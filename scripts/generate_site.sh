#!/bin/bash

python scripts/resource_list.py resource-list master-document/resource_list.csv > resource_list.html

RESOURCE_DETAILS_PATH="resource-details/" python scripts/resource_list.py resource-details master-document/resource_list.csv

FILTERINGS_PATH="filterings/" python scripts/resource_list.py filterings master-document/resource_list.csv

BACKEND_URL="https://sdtulcmi34dt5isrzeha65v7ja0mxdty.lambda-url.eu-north-1.on.aws/add" python scripts/resource_list.py add-resource > add_resource.html

BACKEND_URL="https://sdtulcmi34dt5isrzeha65v7ja0mxdty.lambda-url.eu-north-1.on.aws/edit" EDITS_PATH="edits/" python scripts/resource_list.py edit-resource master-document/resource_list.csv

python scripts/resource_list.py success addition > addition_success.html

python scripts/resource_list.py success edit > edit_success.html

python scripts/resource_list.py failure addition > addition_failure.html

python scripts/resource_list.py failure edit > edit_failure.html
