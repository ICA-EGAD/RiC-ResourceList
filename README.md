RiC Resource List
=================

Overview
--------

A little web tool over the top of the data in `master-document/resource_list.csv`. It is a static website: upon any changes to `master-document/resource_list.csv`, the script `scripts/resource_list.py` should be run a number of times to regenerate all of the HTML files (see below for details).

- The landing page (list of resources containing a few summary details) is `resource_list.html`.
- The landing page offers the possibility to filter by resource type; the resulting lists in each case are to be found in `filterings/`.
- Adding a new resource is via the form at `add_resource.html`, which is also linked to from the landing page.
- For each resource in the list at the landing page, one can click to obtain full details. The corresponding pages are at `resource-details/`.
- For each resource in the list at the landing page, one can edit its details. The corresponding pages are at `edits/`. The edit page for a given resource is linked to from the page with the full details of this resource.
- The CSS of the entire site is defined by `ric_resources.css`. No Javascript is used.

Intended flow for adding/editing resources
------------------------------------------

A pull request should be made with an edit to `master-document/resource_list.csv`. When this pull request is merged in, a github action should be executed which runs the script `scripts/resource_list.py` as needed to regenerate the site.

Such a pull request can be made manually, but a backend will also be set up which provides an endpoint for the forms for adding or editing a resource to call; this backend will edit the CSV programmatically and make a pull request.

Regenerating the site
---------------------

The script at `scripts/resource_list.py` should be run several times as follows, setting `BACKEND_URL` to the appropriate URLs. It is assumed below that one is running from within the `scripts` directory; this is not necessary, but the various paths must then be adjusted accordingly.

```
python resource_list.py resource-list ../master-document/resource_list.csv > ../resource_list.html

RESOURCE_DETAILS_PATH="../resource-details/" python resource_list.py resource-details ../master-document/resource_list.csv

FILTERINGS_PATH=../filterings python resource_list.py filterings ../master-document/resource_list.csv

BACKEND_URL="" python resource_list.py add-resource > ../add_resource.html

BACKEND_URL="" EDITS_PATH=../edits python resource_list.py edit-resource ../master-document/resource_list.csv

python resource_list.py success addition > ../addition_success.html

python resource_list.py success edit > ../edit_success.html

python resource_list.py failure addition > ../addition_failure.html

python resource_list.py failure edit > ../edit_failure.html

```
