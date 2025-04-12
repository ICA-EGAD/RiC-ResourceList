Lambda instructions
=======================

Deployment
----------

If only the file `handle_submission.py` has changed, the simplest way to create
a zip file appropriate for uploading is to download the old one (if you do
not already have it), rename it to `handle_submission.zip`, run

```
zip handle_submission.zip handle_submission.py
```

and then re-upload `handle_submission.zip`.

To create the zip file for upload from scratch, one can proceed as follows.
Various of the steps can be omitted in future iterations if they have already
been carried out. The private key file must be named exactly as indicated; it
can be downloaded from the EGAD organisation Settings page at GitHub.

```
mkdir package
cd package
zip -r ../handle_submission.zip .
cd ../
zip handle_submission.zip egad_github_app_private_key.pem
zip handle_submission.zip handle_submission.py
```

Rate limiting
-------------

To avoid the possibility of costs spiralling out of control, the Lambda will
shut itself down if used too often. The shutting down can be undone manually
in AWS by navigating to 'Configuration -> Concurrency and recursion detection'
and setting 'Concurrency -> Function concurrency' to
'Use unreserved account concurrency'.

