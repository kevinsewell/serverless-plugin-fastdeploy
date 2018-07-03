import base64
import io
import zipfile
import boto3
import glob
import os

os.environ["AWS_PROFILE"] = "aronim"

from fast_deploy import fast_deploy

lambda_ = boto3.client("lambda")

patterns_ = ["module_one/**"]
service_directory_ = "../example/"

filenames_ = []

for pattern_ in patterns_:
    filenames_.extend(glob.glob(service_directory_ + pattern_))

bytes_io_ = io.BytesIO()
zip_file_ = zipfile.ZipFile(bytes_io_, mode="w")

for filename_ in filenames_:
    entry_name_ = filename_.replace(service_directory_, "")
    zip_file_.write(filename_, arcname=entry_name_)

zip_file_.close()
bytes_ = bytes_io_.getvalue()
base_64_encoded_bytes_ = base64.b64encode(bytes_)

print()

response_ = fast_deploy({
    "serviceName": "Aronim-Example",
    "deploymentStage": "Test",
    "deploymentS3BucketName": "aronim-serverless",
    "base64EncodedZipFileBytes": base_64_encoded_bytes_,
    "globPatterns": patterns_,
    "forceCreateNewBaseDeploymentPackage": False
})

lambda_.update_function_code(
    FunctionName="Aronim-Example-Test-Hello",
    S3Bucket="aronim-serverless",
    S3Key=response_["s3ObjectKey"],
    Publish=True
)
