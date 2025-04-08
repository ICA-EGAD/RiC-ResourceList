AWS Lambda instructions
=======================

Deployment
----------

The following can be run to create a zip file appropriate for uploading. Various
of the steps can be omitted in future iterations if they have already been
carried out. The private key file must be named exactly as indicated; it can
be downloaded from the EGAD organisation Settings page at GitHub.

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

