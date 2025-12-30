"""
A tool which generates the static files of the Resource List website. Organised
into several sub-commands which generate different parts of the website.
"""

# pylint: disable=too-many-lines

from argparse import ArgumentParser
from csv import DictReader
from datetime import datetime, timezone
from os import environ
from pathlib import Path
from re import match as regex_match, split as regex_split
from string import Template
from sys import exit as sys_exit
from typing import Any, Callable, Generator, TypeVar
from urllib.parse import urlparse as parse_url

CSS_FILE_NAME = "ric_resources.css"
EDITS_DIRECTORY_NAME = "edits"
ICONS_DIRECTORY_NAME = "icons"
LOGO_FILE_NAME = "EGAD_logo.svg"
RESOURCE_DETAILS_DIRECTORY_NAME = "resource-details"

_site_template = Template("""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Records in Contexts — Resource List</title>
    <link rel="stylesheet" href="$css_path">$javascript
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
  </head>
  <body>
    <div class="header">
      <a href="$resource_list_path" class="title"><h1>Records in Contexts — Resource List</h1></a>
    </div>
    <div class="ric-links">
      <p><span><a href="https://www.ica.org/resource/records-in-contexts-conceptual-model/">RiC-CM</a></span><span><a href="https://www.ica.org/standards/RiC/ontology">RiC-O</a></span><span class="last"><a href="https://groups.google.com/g/Records_in_Contexts_users">RiC users group</a></span></p>
    </div>
    <div class="egad-logo">
      <img class="egad-logo" src="$logo_path"/>
    </div>$introduction
    <div class="menu" id="menu">
$add_or_edit_menu
$filter_menu
    </div>
$content
  </body>
</html>""")

_JAVASCRIPT_HTML = """
    <script src="ric_resources.js" async></script>"""

_RESOURCE_LIST_INTRODUCTION_HTML = """
    <div class="introduction">
      <p>A list of resources in which <a href="https://www.ica.org/ica-network/expert-groups/egad/records-in-contexts-ric/">Records in Contexts</a> (RiC) is used or discussed, sorted reverse chronologically. The list is built collaboratively by the RiC user community, and managed by EGAD. It is far from exhaustive — please contribute using the 'Add' button!</p>

      <p>This list includes only a few details for each resource (e.g. not a full bibliographic reference in the case of articles) but more details can be obtained by clicking on a resource. The buttons below can be used to filter by resource type.</p>
    </div>"""

_RESOURCE_DETAILS_INTRODUCTION_HTML = """    <div class="introduction">
      <p>Use the green button to edit the resource (moderated: it may take a few days before changes appear).</p>
    </div>"""

_ADD_RESOURCE_INTRODUCTION_HTML = """    <div class="introduction">
      <p>Please fill in the form with the details of the resource you wish to add. The first five fields (up to and including 'Description') are required. The submission will be checked by moderators, and the new resource should appear in the list in a few days.</p>
    </div>"""

_EDIT_RESOURCE_INTRODUCTION_HTML = """    <div class="introduction">
      <p>Please make use of the form to edit the details of the resource you wish to add. The first five fields (up to and including 'Description') are required. The submission will be checked by moderators, and the edits should appear in a few days.</p>
    </div>"""

_FAILURE_HTML = """    <div class="failure">
      <p>An error occurred. Please contact us by raising an <a href="https://github.com/ICA-EGAD/RiC-ResourceList/issues">Issue</a> at GitHub, or otherwise. We will look into it as soon as we can!</p>
      <p class="return-to-resource-list"><a href="./index.html">Return to the resource list</a></p>
    </div>"""

_add_or_edit_menu_html_template = Template("""      <span class="add-edit-menu">
$components
      </span>""")


_add_or_edit_menu_components = {
    "add": Template("""        <a href="$add_resource_path/add_resource.html" class="add-or-edit-link"><figure><img class="icon" src="$icons_path/add.svg" alt="Add resource" id="add-resource" title="Add a resource to the list"/><figcaption>Add</figcaption></figure></a>"""),  # pylint: disable=line-too-long
    "edit": Template("""        <a href="$edit_resource_path/$resource_id.html" class="add-or-edit-link"><figure><img class="icon" src="$icons_path/edit.svg" alt="Edit resource" title="Edit the resource"/><figcaption>Edit</figcaption></figure></a>""")  # pylint: disable=line-too-long
}

_filter_menu_html_template = Template("""      <span class="filter-menu">
$components
      </span>""")

_filter_menu_components = {
    "article": Template("""        <a href="$articles_path" class="filter-link"><figure><img class="$css_class" src="$icons_path/article.svg" alt="Articles" title="Journal articles discussing RiC" id="filter-articles"/><figcaption>Articles</figcaption></figure></a>"""),  # pylint: disable=line-too-long
    "tool": Template("""        <a href="$tools_path" class="filter-link"><figure><img class="$css_class" src="$icons_path/tool.svg" alt="Tools" id="filter-tools" title="Software, APIs, libraries, etc, which may be useful when working with RiC"/><figcaption>Tools</figcaption></figure></a>"""),  # pylint: disable=line-too-long
    "event": Template("""        <a href="$events_path" class="filter-link"><figure><img class="$css_class" src="$icons_path/event.svg" alt="Events" id="filter-events" title="Conferences, workshops, etc, in which RiC is a topic"/><figcaption>Events</figcaption></figure></a>"""),  # pylint: disable=line-too-long
    "thesis": Template("""        <a href="$theses_path" class="filter-link"><figure><img class="$css_class" src="$icons_path/thesis.svg" alt="Theses" id="filter-theses" title="Theses (doctoral, master, ...) which have RiC as their subject (at least partly)"/><figcaption>Theses</figcaption></figure></a>"""),  # pylint: disable=line-too-long
    "web application": Template("""        <a href="$applications_path" class="filter-link"><figure><img class="$css_class" src="$icons_path/web_application.svg" alt="Applications" id="filter-applications" title="Applications, e.g. on the web, which make use of RiC in their implementation"/><figcaption>Apps</figcaption></figure></a>"""),  # pylint: disable=line-too-long
    "dataset": Template("""        <a href="$datasets_path" class="filter-link"><figure><img class="$css_class" src="$icons_path/dataset.svg" alt="Datasets" id="filter-datasets" title="Datasets in RDF, OWL, or other formats in which RiC is involved"/><figcaption>Datasets</figcaption></figure></a>""")  # pylint: disable=line-too-long
}

_resource_list_html_template = Template(
    """    <div class="resource-list" id="resource-list">
      <ul class="resource-list">$list_entries
      </ul>
    </div>
    <div class="last-updated">
      <p>Last updated: <span class="last-updated-timestamp">$last_updated</a></p>
    </div>""")

_resource_entry_template = Template("""
        <li class="resource"><a href="$resource_details_path/$resource_id.html" class="resource-link"><img class="inline-icon" src="$icons_path/$resource_icon" alt="$resource_icon_alt"/><span class="resource-list-title">$title</span>. $responsible. $date.</a></li>""")  # pylint: disable=line-too-long

_resource_details_html_template = Template(
    """    <div class="resource-details" id="resource-details">
      <h2><img class="resource-details-icon" src="$resource_icon" alt="$resource_icon_alt"/>$title</h2>
      <ul>$alternative_title
        <li><span class="resource-details-responsible">$responsible</span></li>
        <li>$date</li>
        <li>$description</li>$remainder
      </ul>
    </div>""")  # pylint: disable=line-too-long

_add_resource_html_template = Template("""    <div class="add-resource">
      <form action="$backend_url" method="post">
        <div class="add-resource-section">
          <label for="title">Title <span class="format-instruction">(can be provided in more than one language, each ending in a language tag such as [en], separated by |)</label>
          <input type="text" id="title" name="title" value="$title_value" required/>
        </div>
        <div class="add-resource-section">
          <fieldset>
            <legend>Resource type</legend>
            <div class="resource-type">
              <input type="radio" id="application" name="type" value="web application" $checked_application required/>
              <label for="application">Application</label>
            </div>
            <div class="resource-type">
              <input type="radio" id="article" name="type" value="article" $checked_article required/>
              <label for="article">Article</label>
            </div>
            <div class="resource-type">
              <input type="radio" id="dataset" name="type" value="dataset" $checked_dataset required/>
              <label for="dataset">Dataset</label>
            </div>
            <div class="resource-type">
              <input type="radio" id="event" name="type" value="event" $checked_event required/>
              <label for="event">Event</label>
            </div>
            <div class="resource-type">
              <input type="radio" id="thesis" name="type" value="thesis" $checked_thesis required/>
              <label for="thesis">Thesis</label>
            </div>
            <div class="resource-type">
              <input type="radio" id="tool" name="type" value="tool" $checked_tool required/>
              <label for="tool">Tool</label>
            </div>
          </fieldset>
        </div>
        <div class="add-resource-section">
          <label for="responsible">Authors/creators/organisers <span class="format-instruction">(should be separated by |, and a webpage can optionally be provided in parantheses after each, e.g. name (webpage) | other name (webpage))</label>
          <input type="text" id="responsible" name="responsible" value="$responsible_value" required/>
        </div>
        <div class="add-resource-section">
          <label for="publication-date">Dates of publication/release/occurrence <span class="format-instruction">(as YYYY, YYYY-MM, or YYYY-MM-DD, optionally followed by [version n.n], and separated by | if more than one date is provided, e.g. 2023-12 or 2024-03 [version 1.0] | 2024-10 [version 2.0])</span></label>
          <input type="text" id="publication-date" name="publication_date" value="$publication_date_value" required/>
        </div>
        <div class="add-resource-section">
          <label for="description">Description <span class="format-instruction">(simple Markdown syntax can optionally be used, e.g. for links as [text to display](url), and more than one language can be provided, separated by |, each ending with a language tag such as [en])</label>
          <textarea id="description" name="description" rows="10" required/>$description_value</textarea>
        </div>
        <div class="add-resource-section">
          <label for="links">Links <span class="format-instruction">(should be separated by a | symbol, and each either in Markdown format [text to display](url) or a verbatim URL)</span></label>
          <input type="text" id="links" name="links" value="$links_value"/>
        </div>
        <div class="add-resource-section">
          <label for="languages">Languages available in <span class="format-instruction">(should be separated by a | symbol, and short clarifications can be provided in parentheses, e.g. French | English (abstract))</span></label>
          <input type="text" id="languages" name="languages" value="$languages_value"/>
        </div>
        <div class="add-resource-section">
          <fieldset>
            <legend>Relevant parts of RiC <span class="format-instruction">(ignoring patch versions, i.e. treating n.n.n as n.n)</span></legend>
            <div class="ric-part">
              <input type="checkbox" id="ric-cm-1-0" name="relevant_parts_of_ric" value="RiC-CM 1.0" $checked_ric_cm_1_0/>
              <label for="ric-cm-1-0">RiC-CM 1.0</label>
            </div>
            <div class="ric-part">
              <input type="checkbox" id="ric-cm-0-2" name="relevant_parts_of_ric" value="RiC-CM 0.2" $checked_ric_cm_0_2/>
              <label for="ric-cm-0-2">RiC-CM 0.2</label>
            </div>
            <div class="ric-part">
              <input type="checkbox" id="ric-o-1-0" name="relevant_parts_of_ric" value="RiC-O 1.0" $checked_ric_o_1_0/>
              <label for="ric-o-1-0">RiC-O 1.0</label>
            </div>
            <div class="ric-part">
              <input type="checkbox" id="ric-o-0-2" name="relevant_parts_of_ric" value="RiC-O 0.2" $checked_ric_o_0_2/>
              <label for="ric-o-0-2">RiC-O 0.2</label>
            </div>
            <div class="ric-part">
              <input type="checkbox" id="ric-other" name="relevant_parts_of_ric" value="Other" $checked_ric_other/>
              <label for="ric-other">Other</label>
            </div>
          </fieldset>
        </div>
        <div class="add-resource-section">
          <label for="prospects">Prospects / status</label>
          <textarea id="prospects" name="prospects" rows="10"/>$prospects_value</textarea>
        </div>
        <div class="add-resource-section">
          <label for="contact">Contacts <span class="format-instruction">(should be separated by a | symbol, can e.g. be an email address)</span></label>
          <input type="text" id="contact" name="contact" value="$contact_value"/>
        </div>
        <div class="add-resource-section">
          <label for="related-to">Related resources <span class="format-instruction">(should be separated by a | symbol, and can be either be the URL of another resource in the list, or be in the format #n, where n is the number at the end of such an URL)</span></label>
          <input type="text" id="related-to" name="related_to" value="$related_to_value"/>
        </div>$id_field
        <div class="add-resource-section add-resource-section-button">
          <input type="submit" class="add-button" value="$submit_value"/>
        </div>
      </form>
    </div>""")

_success_html_template = Template("""    <div class="success">
      <p>Resource $action successfully submitted! A pull request should in the next few minutes be generated <a href="https://github.com/ICA-EGAD/RiC-ResourceList/pulls">at GitHub</a>, which EGAD will review. Once the pull request is approved (it may take a few days for us to get to it!), the submission will be deployed to the resource list and become visible there.</p>
      <p class="return-to-resource-list"><a href="./index.html">Return to the resource list</a></p>
    </div>""")


AlternativeTitle = str
Date = str
HTML = str
ResourceId = str
ResourceType = str
RiCPart = str
Row = dict[str, str]
Title = str
Version = str
Word = str
URL = str

T = TypeVar("T", tuple[HTML, ResourceId], tuple[HTML, Date, ResourceType])

_type = {
    "article": "Journal article",
    "dataset": "Dataset",
    "event": "Event",
    "thesis": "Thesis",
    "tool": "Tool",
    "web application": "Application"
}

_responsible_keys = {
    "Application": "Maintainers",
    "Dataset": "Authors",
    "Event": "Responsible",
    "Journal article": "Authors",
    "Thesis": "Author",
    "Tool": "Maintainers"
}

_date_keys = {
    "Application": "Released",
    "Dataset": "Published",
    "Event": "Takes/took place",
    "Journal article": "Published",
    "Thesis": "Published",
    "Tool": "Released"
}

_resource_icons = {
    "article": "article.svg",
    "dataset": "dataset.svg",
    "event": "event.svg",
    "thesis": "thesis.svg",
    "tool": "tool.svg",
    "web application": "web_application.svg"
}

_languages = {
    "en": "English",
    "fr": "French",
    "ko": "Korean",
    "nl": "Dutch"
}

_resource_type_filters = {
    "article": "articles",
    "dataset": "datasets",
    "event": "events",
    "thesis": "theses",
    "tool": "tools",
    "web application": "applications"
}

class NotALinkException(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)

def _current_timestamp() -> str:
    return datetime.strftime(datetime.now(timezone.utc), "%Y-%m-%d %H:%M (GMT)")


def _is_link(word: str) -> bool:
    try:
        return parse_url(word).scheme in ["http", "https", "ftp"]
    except ValueError:
        return False


def _to_link(word: str | None, url: str, css_class: str | None = None) -> str:
    tidied_url = url
    remainder = ""
    while True:
        if tidied_url[-1] not in [".", ",", "\n", ";", ":", ")"]:
            break
        remainder = tidied_url[-1] + remainder
        tidied_url = tidied_url[:-1]
    if word is None:
        word = tidied_url
    if css_class is None:
        return f"<a href=\"{tidied_url}\">{word}</a>{remainder}"
    return f"<a href=\"{tidied_url}\" class=\"{css_class}\">{word}</a>{remainder}"


def _links_in_text(text: str) -> Generator[Word, None, None]:
    """
    Two kinds of syntax are supported.

    1) If a 'word' (something between spaces) parses to a URL whose scheme is
    http, https, or ftp, then it is converted to a link whose text is the same
    as the URL. If a word ends in '.', ',', ';', '\n', ';', ':', then we
    regard the URL as terminating at the character before this.
    2) If a 'word' is of the form [...], where ... does not contain ], would be
    converted to a link according to 1), then the previous word is converted to
    a link whose underlying URL is ... .
    """
    text = " ".join(_to_link(None, word) if _is_link(word) else word
                    for word in text.split(" "))
    for part in regex_split(r"(\[.+?\]\(.+?\))", text):
        match = regex_match(r"\[(.+?)\]\((.+?)\)", part)
        if match is not None:
            if _is_link(match.group(2)):
                yield f"<a href='{match.group(2)}'>{match.group(1)}</a>"
                continue
        yield part


def _description(row: Row) -> Generator[HTML, None, None]:
    changed_language = False
    language = None
    for description in row["description"].split("|"):
        description = description.strip()
        if description[-1] == "]" and description[-4] == "[":
            language = description[-3:-1]
            if language not in _languages:
                raise ValueError(
                    "The following is not a recognised language: "
                    f"{language}. Occurs in description: {description}")
            description = "".join(_links_in_text(description[:-4].rstrip()))
        else:
            description = "".join(_links_in_text(description))
        for paragraph in description.split("\n\n"):
            paragraph = paragraph.strip()
            if changed_language:
                if language is not None:
                    yield f"<p class='after-language-change'>{paragraph} ({
                        _languages[language]})</p>"
                else:
                    yield f"<p class='after-language-change'>{paragraph}</p>"
                changed_language = False
            elif language is not None:
                yield f"<p>{paragraph}  ({_languages[language]})</p>"
            else:
                yield f"<p>{paragraph}</p>"
        changed_language = True


def _title(row: Row) -> tuple[Title, AlternativeTitle | None]:
    title = row["title"].strip()
    if "|" not in title:
        return title, None
    title_parts = title.split("|")
    if len(title_parts) > 2:
        raise ValueError(f"Too many title parts: {title}")
    for title_part in title_parts:
        title_part = title_part.strip()
        if not (title_part[-1] == "]" and title_part[-4] == "["):
            raise ValueError(
                f"Expecting title part to end in language tag: {title_part}")
        language = title_part[-3:-1]
        if language not in _languages:
            raise ValueError(
                "The following is not a recognised language: "
                f"{language}. Occurs in title part: {title_part}")
    return (
        title_parts[0].strip()[:-4].rstrip(),
        title_parts[1].strip()[:-4].rstrip()
    )

def _parse_link(link: str, css_class: str | None = None) -> str:
    language = None
    if link[-1] == "]" and link[-4] == "[":
        language = link[-3:-1]
        if language not in _languages:
            raise ValueError(
                "The following is not a recognised language: "
                f"{language}. Occurs in link: {link}")
        link = link[:-4].rstrip()
    match = regex_match(r"\[(.+?)\]\((.+?)\)", link)
    if match is None or not _is_link(match.group(2)):
        if not _is_link(link):
            raise NotALinkException(
                f"The following seems not to be a link: {link}")
        link = _to_link(None, link, css_class)
    else:
        link = _to_link(
            match.group(1), match.group(2), css_class)
    if language is not None:
        return f"{link} ({_languages[language]})"
    return link

def _links(row: Row) -> Generator[HTML, None, None]:
    for link in row["links"].split("|"):
        link = link.strip()
        if not link:
            continue
        yield _parse_link(link, "link-from-resource")

def _responsible_without_links(row: Row) -> Generator[HTML, None, None]:
    for responsible in row["responsible"].split("|"):
        responsible = responsible.strip()
        if "(" in responsible:
            yield responsible.split("(", 1)[0].rstrip()
        else:
            yield responsible


def _responsible_with_links(row: Row) -> Generator[HTML, None, None]:
    for responsible in row["responsible"].split("|"):
        responsible = responsible.strip()
        if "(" in responsible:
            if responsible[-1] != ")":
                raise ValueError(
                    f"Expecting the following to end in ): {responsible}")
            entity, link = responsible[:-1].split("(", 1)
            try:
                link = _parse_link(link)
            except NotALinkException:
                yield responsible
                continue
            yield (f"{entity.strip()} <span class=\"responsible-webpage\">"
                   f"({link})</span>")
        else:
            yield responsible


def _dates(row: Row) -> Generator[tuple[HTML, Version | None], None, None]:
    dates = row["publication_date"].split("|")
    if len(dates) == 1 and "[" not in dates[0]:
        yield row["publication_date"].strip(), None
        return
    for date in dates:
        date, version = date.split("[")
        date = date.strip()
        version = version.strip()
        if version[-1] != "]":
            raise ValueError(
                f"Missing ] at end of date with version: {date}")
        if not version.startswith("version"):
            raise ValueError(
                "Expecting all version strings to start with 'version': "
                f"{dates}")
        version = version[:-1].lstrip("version").strip()
        yield date, version


def _available_languages(row: Row) -> HTML | None:
    languages = row["languages"]
    if not languages:
        return None
    available_or_held = "Held" if row["type"] == "event" else "Available"
    return f"{available_or_held} in: {", ".join(
        language.strip() for language in languages.split("|"))}"


def _relevant_parts_of_ric(row: Row) -> HTML | None:
    relevant_parts = row["relevant_parts_of_ric"]
    if not relevant_parts:
        return None
    return " ".join(f"<span class=\"ric-part\">{ric_part.strip()}</span>"
                    for ric_part in relevant_parts.split("|"))


def _related_to(row: Row) -> Generator[HTML, None, None]:
    related_to = row["related_to"]
    if not related_to:
        return
    for resource in related_to.split("|"):
        resource = resource.strip()
        if resource[0] != "#":
            raise ValueError(
                "Expecting the following 'related_to' entry to begin with #: "
                f"{resource}")
        resource_id = resource[1:]
        yield (f"<a href=\"../resource-details/{resource_id}.html\" "
               f"class=\"related-to\">#{resource_id}</a>")


def _remainder(row: Row) -> HTML:
    remainder = ""
    for link in _links(row):
        remainder += "\n" + " "*8 + f"<li>{link}</li>"
    languages = _available_languages(row)
    if languages is not None:
        remainder += "\n" + " "*8 + f"<li>{languages}</li>"
    relevant_parts_of_ric = _relevant_parts_of_ric(row)
    if relevant_parts_of_ric is not None:
        remainder += "\n" + " "*8 + f"<li>{relevant_parts_of_ric}</li>"
    prospects = row["prospects"]
    if prospects:
        remainder += "\n" + " "*8 + f"<li>{prospects}</li>"
    contact = row["contact"]
    if contact:
        contacts = ", ".join(
            f"<span class=\"contact-details\">{
                part.strip().replace('@', ' (at) ')}</span>"
            for part in contact.split("|"))
        remainder += "\n" + " "*8 + f"<li>Contact: {contacts}</li>"
    related_to = ", ".join(_related_to(row))
    if related_to:
        remainder += "\n" + " "*8 + f"<li>Relates to RiC resources: {
            related_to}</li>"
    return remainder


def _resource_details(row: Row) -> tuple[HTML, ResourceId]:
    resource_type = _type[row["type"]]
    title, alternative_title = _title(row)
    if alternative_title is not None:
        alternative_title = "\n" + " "*8 + f"({alternative_title})"
    else:
        alternative_title = ""
    description = "\n\n            ".join(_description(row))
    versioned_dates = list(_dates(row))
    if len(versioned_dates) == 1:
        date, version = versioned_dates[0]
        dates = f"{date} (v{version})" if version is not None else date
    else:
        dates = "<ul>"
        for date, version in versioned_dates:
            if version is not None:
                dates += f"<li class=\"version\">{date} (v{version})</li>"
            else:
                dates += f"<li class=\"version\">{date}</li>"
    "".join(
        f"<span class='resource-details-date'>{date} (v{version})</span>"
        if version is not None else f"<span class='resource-details-date'>{
            date}</span>"
        for date, version in _dates(row))
    if row["type"] != "article":
        responsibles = list(_responsible_with_links(row))
        if len(responsibles) == 1:
            responsible = responsibles[0]
        else:
            responsible = "<ul>"
            responsible += "".join(
                f"<li class=\"responsible\">{part}</li>"
                for part in responsibles)
            responsible += "</ul>"
    else:
        responsible = ", ".join(_responsible_with_links(row))
    resource_id = row["id"]
    resource_details_html = _resource_details_html_template.substitute(
        resource_id=resource_id,
        resource_icon=f"../{ICONS_DIRECTORY_NAME}/{
            _resource_icons[row["type"]]}",
        resource_icon_alt=resource_type,
        title=title,
        alternative_title=alternative_title,
        responsible=responsible,
        date=dates,
        description=description,
        remainder=_remainder(row)
    )
    return _site_template.substitute(
        css_path=f"../{CSS_FILE_NAME}",
        logo_path=f"../{LOGO_FILE_NAME}",
        icons_path=f"../{ICONS_DIRECTORY_NAME}",
        resource_list_path="../index.html",
        javascript="",
        introduction=_RESOURCE_DETAILS_INTRODUCTION_HTML,
        add_or_edit_menu=_add_or_edit_menu_html_template.substitute(
            components=_add_or_edit_menu_components["edit"].substitute(
                edit_resource_path=f"../{EDITS_DIRECTORY_NAME}",
                resource_id=resource_id,
                icons_path=f"../{ICONS_DIRECTORY_NAME}")),
        filter_menu="",
        content=resource_details_html), resource_id


def _resource(row, icons_path: str, resource_details_path: str) -> tuple[
        HTML, Date, ResourceType]:
    title, _ = _title(row)
    if row["type"] != "article":
        responsible = " and ".join(_responsible_without_links(row))
    else:
        responsible = ", ".join(_responsible_without_links(row))
    versioned_dates = list(_dates(row))
    dates = ", ".join(f"{date} (v{version})" if version is not None else date
                      for date, version in versioned_dates)
    earliest_date, _ = versioned_dates[0]
    return _resource_entry_template.substitute(
        resource_id=row["id"],
        icons_path=icons_path,
        resource_details_path=resource_details_path,
        resource_icon=_resource_icons[row["type"]],
        resource_icon_alt=_type[row["type"]],
        title=title,
        responsible=responsible,
        date=dates,
    ), earliest_date, row["type"]


def _process_master_document(
        path_to_csv: Path,
        row_processor: Callable[[Any], T]) -> Generator[T, None, None]:
    with open(path_to_csv, "r", encoding="utf-8") as csv_file:
        csv_reader = DictReader(csv_file)
        for row in csv_reader:
            yield row_processor(row)


def resource_list(path_to_csv: Path) -> HTML:
    """
    Generates the HTML for the resource list (landing page of the website)
    """
    list_entries_with_date = list(_process_master_document(
        path_to_csv,
        lambda row: _resource(
            row,
            ICONS_DIRECTORY_NAME,
            RESOURCE_DETAILS_DIRECTORY_NAME)))
    list_entries_with_date.sort(key=lambda entry: entry[1], reverse=True)
    list_entries = "".join(
        [resource for resource, _, _ in list_entries_with_date])
    return _site_template.substitute(
        css_path=CSS_FILE_NAME,
        logo_path=LOGO_FILE_NAME,
        icons_path=ICONS_DIRECTORY_NAME,
        resource_list_path="",
        javascript="",
        introduction=_RESOURCE_LIST_INTRODUCTION_HTML,
        add_or_edit_menu=_add_or_edit_menu_html_template.substitute(
            components=_add_or_edit_menu_components["add"].substitute(
                add_resource_path=".",
                icons_path=ICONS_DIRECTORY_NAME)),
        filter_menu=_filter_menu_html_template.substitute(
            components="\n".join(
                template.substitute(
                    applications_path="filterings/applications.html",
                    articles_path="filterings/articles.html",
                    datasets_path="filterings/datasets.html",
                    events_path="filterings/events.html",
                    theses_path="filterings/theses.html",
                    tools_path="filterings/tools.html",
                    icons_path=ICONS_DIRECTORY_NAME,
                    css_class="icon")
                for template in _filter_menu_components.values())),
        content=_resource_list_html_template.substitute(
            list_entries=list_entries,
            last_updated=_current_timestamp())
    )


def resource_details(path_to_csv: Path, path_to_resource_details: Path) -> None:
    """
    Generates HTML files with the details of each resource, one for each
    resource, saving them into a directory specified in an environment
    variable
    """
    for resource_details_html, resource_id in _process_master_document(
            path_to_csv, _resource_details):
        with open(
                path_to_resource_details / f"{resource_id}.html",
                "w",
                encoding="utf-8") as resource_details_file:
            resource_details_file.write(resource_details_html)


def add_resource(backend_url: URL) -> HTML:
    """
    Generates the HTML of the page for adding a resource. Requires an
    environment variable specifying the URL of the backend.
    """
    return _site_template.substitute(
        css_path=CSS_FILE_NAME,
        logo_path=LOGO_FILE_NAME,
        resource_list_path="index.html",
        javascript="",
        introduction=_ADD_RESOURCE_INTRODUCTION_HTML,
        add_or_edit_menu="",
        filter_menu="",
        content=_add_resource_html_template.substitute(
            backend_url=backend_url,
            title_value="",
            checked_application="",
            checked_article="",
            checked_dataset="",
            checked_event="",
            checked_thesis="",
            checked_tool="",
            responsible_value="",
            publication_date_value="",
            description_value="",
            links_value="",
            languages_value="",
            checked_ric_cm_1_0="",
            checked_ric_cm_0_2="",
            checked_ric_o_1_0="",
            checked_ric_o_0_2="",
            checked_ric_other="",
            prospects_value="",
            contact_value="",
            related_to_value="",
            id_field="",
            submit_value="Add")
    )


def _css_class(filter_type: ResourceType, resource_type: ResourceType) -> str:
    if filter_type != resource_type:
        return "icon inline-icon-grayscale"
    return "icon"


def _filtering_path(
        filter_type: ResourceType, resource_type: ResourceType) -> str:
    if filter_type != resource_type:
        return f"{_resource_type_filters[resource_type]}.html"
    return "../index.html"


def filterings(path_to_csv: Path, path_to_filterings: Path) -> None:
    """
    Generates HTML files for filterings of the resource list, one for each
    filtering, saving them into a directory specified in an environment
    variable
    """
    list_entries_with_date = list(_process_master_document(
        path_to_csv,
        lambda row: _resource(
            row,
            f"../{ICONS_DIRECTORY_NAME}",
            f"../{RESOURCE_DETAILS_DIRECTORY_NAME}")))
    list_entries_with_date.sort(key=lambda entry: entry[1], reverse=True)
    for filter_type, plural in _resource_type_filters.items():
        list_entries = "".join(
            [resource for resource, _, resource_type in list_entries_with_date
             if resource_type == filter_type])
        plural += ".html"
        with open(
                path_to_filterings / plural,
                "w",
                encoding="utf-8") as filtering_file:
            filtering_file.write(
                _site_template.substitute(
                    css_path=f"../{CSS_FILE_NAME}",
                    logo_path=f"../{LOGO_FILE_NAME}",
                    icons_path=f"../{ICONS_DIRECTORY_NAME}",
                    resource_list_path="../index.html",
                    javascript="",
                    introduction=_RESOURCE_LIST_INTRODUCTION_HTML,
                    add_or_edit_menu=_add_or_edit_menu_html_template.substitute(
                        components=_add_or_edit_menu_components[
                            "add"].substitute(
                                add_resource_path="..",
                                icons_path=f"../{ICONS_DIRECTORY_NAME}")),
                    filter_menu=_filter_menu_html_template.substitute(
                        components="\n".join(
                            template.substitute(
                                applications_path=_filtering_path(
                                    filter_type, "web application"),
                                articles_path=_filtering_path(
                                    filter_type, "article"),
                                datasets_path=_filtering_path(
                                    filter_type, "dataset"),
                                events_path=_filtering_path(
                                    filter_type, "event"),
                                theses_path=_filtering_path(
                                    filter_type, "thesis"),
                                tools_path=_filtering_path(
                                    filter_type, "tool"),
                                icons_path=f"../{ICONS_DIRECTORY_NAME}",
                                css_class=_css_class(
                                    filter_type, resource_type))
                            for resource_type, template in
                            _filter_menu_components.items())),
                    content=_resource_list_html_template.substitute(
                        list_entries=list_entries,
                        last_updated=_current_timestamp())
                )
            )


def _checked_type(row, resource_type: ResourceType) -> str:
    if row["type"].strip() == resource_type:
        return "checked"
    return ""


def _ric_parts_to_check(row: Row) -> Generator[RiCPart, None, None]:
    for part in row["relevant_parts_of_ric"].split("|"):
        part = part.strip()
        found = False
        for ric_part in [
                "RiC-CM 1.0", "RiC-CM 0.2", "RiC-O 1.0", "RiC-O 0.2"]:
            if part == ric_part:
                yield ric_part
                found = True
        if not found:
            yield "Other"


def _checked_ric_part(
        ric_parts_to_check: list[RiCPart], ric_part: RiCPart) -> str:
    if ric_part in ric_parts_to_check:
        return "checked"
    return ""


def edits(
        backend_url: URL,
        path_to_edits: Path,
        path_to_csv: Path) -> None:
    """
    Generates HTML files for editing resource details, one for each
    resource, saving them into a directory specified in an environment
    variable. Requires an environment variable specifying the URL of the
    backend.
    """
    with open(path_to_csv, "r", encoding="utf-8") as csv_file:
        csv_reader = DictReader(csv_file)
        for row in csv_reader:
            resource_id = row["id"]
            id_field = f"<input type=\"hidden\" name=\"id\" value=\"{
                resource_id}\">"
            ric_parts = list(_ric_parts_to_check(row))
            with open(
                    path_to_edits / f"{resource_id}.html",
                    "w",
                    encoding="utf-8") as edit_file:
                edit_file.write(_site_template.substitute(
                    css_path=f"../{CSS_FILE_NAME}",
                    logo_path=f"../{LOGO_FILE_NAME}",
                    resource_list_path="../index.html",
                    javascript="",
                    introduction=_EDIT_RESOURCE_INTRODUCTION_HTML,
                    add_or_edit_menu="",
                    filter_menu="",
                    content=_add_resource_html_template.substitute(
                        backend_url=backend_url,
                        title_value=row["title"],
                        checked_application=_checked_type(
                            row, "web application"),
                        checked_article=_checked_type(row, "article"),
                        checked_dataset=_checked_type(row, "dataset"),
                        checked_event=_checked_type(row, "event"),
                        checked_thesis=_checked_type(row, "thesis"),
                        checked_tool=_checked_type(row, "tool"),
                        responsible_value=row["responsible"],
                        publication_date_value=row["publication_date"],
                        description_value=row["description"],
                        links_value=row["links"],
                        languages_value=row["languages"],
                        checked_ric_cm_1_0=_checked_ric_part(
                            ric_parts, "RiC-CM 1.0"),
                        checked_ric_cm_0_2=_checked_ric_part(
                            ric_parts, "RiC-CM 0.2"),
                        checked_ric_o_1_0=_checked_ric_part(
                            ric_parts, "RiC-O 1.0"),
                        checked_ric_o_0_2=_checked_ric_part(
                            ric_parts, "RiC-O 0.2"),
                        checked_ric_other=_checked_ric_part(
                            ric_parts, "Other"),
                        prospects_value=row["prospects"],
                        contact_value=row["contact"],
                        related_to_value=row["related_to"],
                        id_field=id_field,
                        submit_value="Edit"
                    )
                ))


def success(action: str) -> HTML:
    """
    Generates the HTML of the page redirected to following a successful
    submission of a resource addition or edit.
    """
    return _site_template.substitute(
        css_path=CSS_FILE_NAME,
        logo_path=LOGO_FILE_NAME,
        resource_list_path="./index.html",
        javascript="",
        introduction="",
        add_or_edit_menu="",
        filter_menu="",
        content=_success_html_template.substitute(action=action)
    )


def failure() -> HTML:
    """
    Generates the HTML of the page redirected to following a failed
    submission of a resource addition or edit.
    """
    return _site_template.substitute(
        css_path=CSS_FILE_NAME,
        logo_path=LOGO_FILE_NAME,
        resource_list_path="./index.html",
        javascript="",
        introduction="",
        add_or_edit_menu="",
        filter_menu="",
        content=_FAILURE_HTML
    )


def _arguments_parser() -> ArgumentParser:
    argument_parser = ArgumentParser(
        description=(
            "For generating the HTML pages of the RiC resource site from "
            "the master spreadsheet"
        )
    )
    subparsers = argument_parser.add_subparsers(
        dest="subcommand")
    resource_list_subparser = subparsers.add_parser(
        "resource-list",
        help="For generating the landing page with the summary resource "
        "list. Outputs the HTML of the page to stdout")
    resource_details_subparser = subparsers.add_parser(
        "resource-details",
        help="For generating the individual pages with details of the "
        "resources. The environment variable RESOURCE_DETAILS_PATH "
        "must be provided, which should be a path to a directory in "
        "which to write the generated pages to")
    subparsers.add_parser(
        "add-resource",
        help="For generating the page for adding a resource. Outputs the "
        "HTML of the page to stdout. The environment variable "
        "BACKEND_URL must be provided, which should be the URL of "
        "the backend endpoint to which the POST made when submitting "
        "the form to add a resource is to be sent")
    filter_subparser = subparsers.add_parser(
        "filterings",
        help="For generating pages which are filterings of the summary "
        "resource list by resource type. The environment variable "
        "FILTERINGS_PATH must be provided, which should be a path to a "
        "directory in which to write the generated pages to")
    edit_resource_subparser = subparsers.add_parser(
        "edit-resource",
        help="For generating the pages for editing a resource. The "
        "environment variable EDITS_PATH must be provided, which should "
        "be a path to a directory in which to write the generated pages "
        "to. The environment variable BACKEND_URL must also be "
        "provided, which should be the URL of the backend endpoint to "
        "which the POST made when submitting the form to edit a "
        "resource is to be sent")
    success_subparser = subparsers.add_parser(
        "success",
        help="For generating the page redirected to upon successful "
             "submission of an addition or edit. Outputs the HTML of the "
             "page to stdout")
    subparsers.add_parser(
        "failure",
        help="For generating the page redirected to upon failure of the "
             "submission of an addition or edit. Outputs the HTML of the "
             "page to stdout")
    resource_list_subparser.add_argument(
        "path_to_master_document",
        type=Path,
        help="Path to the CSV master document for the resource list")
    resource_details_subparser.add_argument(
        "path_to_master_document",
        type=Path,
        help="Path to the CSV master document for the resource list")
    filter_subparser.add_argument(
        "path_to_master_document",
        type=Path,
        help="Path to the CSV master document for the resource list")
    edit_resource_subparser.add_argument(
        "path_to_master_document",
        type=Path,
        help="Path to the CSV master document for the resource list")
    success_subparser.add_argument(
        "action",
        type=str,
        choices=["addition", "edit"],
        help="Whether the success page is for an addition or an edit")
    return argument_parser


# pylint: disable=too-many-branches
def _main() -> None:
    arguments = _arguments_parser().parse_args()
    if arguments.subcommand == "resource-list":
        print(resource_list(arguments.path_to_master_document))
    elif arguments.subcommand == "resource-details":
        try:
            path_to_resource_details = Path(environ["RESOURCE_DETAILS_PATH"])
        except KeyError:
            sys_exit("The environment variable RESOURCE_DETAILS_PATH must "
                     "be set")
        resource_details(
            arguments.path_to_master_document,
            path_to_resource_details)
    elif arguments.subcommand == "add-resource":
        try:
            backend_url = environ["BACKEND_URL"]
        except KeyError:
            sys_exit("The environment variable BACKEND_URL must be set")
        print(add_resource(backend_url))
    elif arguments.subcommand == "filterings":
        try:
            path_to_filterings = Path(environ["FILTERINGS_PATH"])
        except KeyError:
            sys_exit("The environment variable FILTERINGS_PATH must be set")
        filterings(
            arguments.path_to_master_document,
            path_to_filterings)
    elif arguments.subcommand == "edit-resource":
        try:
            backend_url = environ["BACKEND_URL"]
        except KeyError:
            sys_exit("The environment variable BACKEND_URL must be set")
        try:
            path_to_edits = Path(environ["EDITS_PATH"])
        except KeyError:
            sys_exit("The environment variable EDITS_PATH must be set")
        edits(backend_url, path_to_edits, arguments.path_to_master_document)
    elif arguments.subcommand == "success":
        print(success(arguments.action))
    elif arguments.subcommand == "failure":
        print(failure())
    else:
        raise ValueError


if __name__ == "__main__":
    _main()
