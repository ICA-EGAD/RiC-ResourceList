RiC Resource List
=================

Usage
-----

Can be browsed as a [website](https://ica-egad.github.io/RiC-ResourceList/index.html). Additions and edits can be made via the website or by making a pull request changing the master document at `master-document/resource_list.csv`.


Architecture
------------

Has the following components.

* A static [website](https://ica-egad.github.io/RiC-ResourceList/index.html), consisting of the HTML files in this repository along with the CSS file. No Javascript is used.
* A master document `master-document/resource_list.csv` from which the static website is generated.
* A very lightweight backend living in the cloud, fired as needed (function-as-a-service), functioning as reverse proxy towards GitHub for adding or editing resources via the website.
* Three GitHub Actions, two of which are triggered by the backend to create a pull request updating the master document upon receipt of a resource addition or edit, and one of which re-generates the site upon the merging of such a pull request.

Guide to the scripts:

* Re-generation of the site is by means of the script `scripts/generated_site.sh`, which calls `scripts/resource_list.py` numerous times.
* The script `scripts/handle_submission.py` defines the on-demand function which serves as the backend/reverse proxy in the cloud.
* The script `scripts/update_master_document.py` handles the form submissions from the website for adding or editing a resource.


Deployment
----------

To make any changes to the GitHub Actions, one can simply edit the relevant files in `scripts` and make a pull request.

Deployment of the cloud backend is covered in the README file in `scripts`.
