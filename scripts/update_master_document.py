"""
Given a form submission for adding a resource, appends a new row to the
master document CSV file with the submitted data. Given a form submission for
editing a resource, replaces the affected row in the master document CSV file
with the submitted data.
"""

from argparse import ArgumentParser
from csv import DictReader as csv_reader, DictWriter as csv_writer
from pathlib import Path
from urllib.parse import parse_qs as parse_form_data

Row = dict[str, str]

FIELDNAMES = [
    "id", "title", "responsible", "description", "publication_date", "type",
    "links", "languages", "status", "relevant_parts_of_ric", "prospects",
    "contact", "related_to"
]

MASTER_DOCUMENT_PATH = Path("master-document") / "resource_list.csv"


def _add_missing_fields(edited: Row, current: Row) -> None:
    for field in FIELDNAMES:
        if field not in edited:
            edited[field] = current[field]


def _largest_id_of_master_document() -> int:
    largest_id = -1
    with open(MASTER_DOCUMENT_PATH, "r", encoding="utf-8") as master_document:
        for row in csv_reader(master_document):
            largest_id = max(int(row["id"]), largest_id)
    return largest_id


def _add(form_submission: str) -> None:
    details = {
        field: " | ".join(values)
        for field, values in parse_form_data(form_submission).items()
    }
    details["id"] = str(_largest_id_of_master_document() + 1)
    with open(MASTER_DOCUMENT_PATH, "a", encoding="utf-8") as master_document:
        csv_writer(
            master_document,
            FIELDNAMES,
            delimiter=",",
            quotechar="\"",
            lineterminator="\n").writerow(details)


def _edit(form_submission: str) -> None:
    details = {
        field: " | ".join(values)
        for field, values in parse_form_data(form_submission).items()
    }
    resource_id = details["id"]
    rows: list[dict[str, str]]
    with open(MASTER_DOCUMENT_PATH, "r", encoding="utf-8") as master_document:
        rows = list(csv_reader(master_document))
    with open(MASTER_DOCUMENT_PATH, "w", encoding="utf-8") as master_document:
        writer = csv_writer(
            master_document,
            FIELDNAMES,
            delimiter=",",
            quotechar="\"",
            lineterminator="\n")
        writer.writeheader()
        for row in rows:
            if row["id"] == resource_id:
                _add_missing_fields(details, row)
                writer.writerow(details)
            else:
                writer.writerow(row)


def _arguments_parser() -> ArgumentParser:
    argument_parser = ArgumentParser(
        description=(
            "Adds or edits the resource list master document according to a "
            "form submission from the Resource List")
    )
    subparsers = argument_parser.add_subparsers(dest="subcommand")
    add_parser = subparsers.add_parser("add", help="Add a resource")
    edit_parser = subparsers.add_parser("edit", help="Edit a resource")
    for parser in [add_parser, edit_parser]:
        parser.add_argument(
            "form_submission",
            type=str,
            help="The string sent in the body of a form submission POST from "
                 "the Resource List")
    return argument_parser


def _main() -> None:
    arguments = _arguments_parser().parse_args()
    form_submission = arguments.form_submission
    if arguments.subcommand == "add":
        _add(form_submission)
    elif arguments.subcommand == "edit":
        _edit(form_submission)
    else:
        raise ValueError


if __name__ == "__main__":
    _main()
