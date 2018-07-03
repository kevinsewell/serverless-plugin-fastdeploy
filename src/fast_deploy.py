import base64
import glob
import io
import logging
import re
import shutil
import tempfile
import time
import zipfile
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

s3_ = boto3.client("s3")

log_ = logging.getLogger("")
log_.setLevel(logging.INFO)

update_package_suffix_ = "FastDeployUpdate"
base_package_suffix_ = "FastDeployBase"


def create_new_deploy_prefix(service_name_, deployment_stage_):
    """
    Get Deployment Folder name

    :return:
    """

    timestamp_millis_ = int(time.time() * 1000)

    datetime_ = datetime.now()
    timestamp_iso_ = datetime_.isoformat()[0:23]

    return "serverless/%s/%s/%s-%sZ" % (service_name_, deployment_stage_, timestamp_millis_, timestamp_iso_)


def append_update_package(base_package_,
                          update_package_):
    """
    Update Package

    :param base_package_:
    :param update_package_:

    :return:
    """

    file_infos_ = update_package_.infolist()

    for file_info_ in file_infos_:
        file_content_ = update_package_.read(file_info_)
        base_package_.writestr(file_info_, file_content_)


def list_service_deployment_prefixes(deployment_s3_bucket_name_,
                                     service_name_,
                                     deployment_stage_):
    """
    List Service Deployments

    :param deployment_s3_bucket_name_:
    :param service_name_:
    :param deployment_stage_:

    :return:
    """

    service_deployments_prefix_ = "serverless/%s/%s/" % (service_name_, deployment_stage_)

    list_objects_v2_request_ = {
        "Bucket": deployment_s3_bucket_name_,
        "Prefix": service_deployments_prefix_,
        "Delimiter": "/"
    }

    response_ = s3_.list_objects_v2(**list_objects_v2_request_)

    if "CommonPrefixes" not in response_:
        return []

    service_deployment_prefixes_ = response_["CommonPrefixes"]

    while "NextContinuationToken" in response_:
        list_objects_v2_request_["ContinuationToken"] = response_["NextContinuationToken"]

        response_ = s3_.list_objects_v2(**list_objects_v2_request_)

        service_deployment_prefixes_.extend(response_["CommonPrefixes"])

    service_deployment_prefixes_ = list(
        map(
            lambda item_: re.sub(r"/$", "", item_["Prefix"]),
            service_deployment_prefixes_
        )
    )

    return service_deployment_prefixes_


def get_latest_deployment_package(deployment_s3_bucket_name_,
                                  service_name_,
                                  deployment_stage_,
                                  deployment_package_name_):
    """
    Get Latest Deployment Package

    :param deployment_s3_bucket_name_:
    :param service_name_:
    :param deployment_stage_:
    :param deployment_package_name_:

    :return:
    """

    service_deployment_prefixes_ = list_service_deployment_prefixes(deployment_s3_bucket_name_,
                                                                    service_name_,
                                                                    deployment_stage_)
    service_deployment_prefixes_.sort(reverse=True)

    for service_deployment_prefix_ in service_deployment_prefixes_:
        base_deployment_s3_object_key_ = service_deployment_prefix_ + "/" + deployment_package_name_
        base_deployment_ = get_s3_object(deployment_s3_bucket_name_, base_deployment_s3_object_key_)

        if base_deployment_ is not None:
            log_.info("Latest deployment package found [{}]".format(base_deployment_s3_object_key_))

            return base_deployment_

    return None


def get_s3_object(s3_bucket_name_, s3_object_key_):
    """
    Get S3 Object

    :param s3_bucket_name_:
    :param s3_object_key_:

    :return:
    """

    try:
        s3_object_ = s3_.get_object(Bucket=s3_bucket_name_, Key=s3_object_key_)

        return s3_object_["Body"].read()

    except ClientError:

        log_.warning("Object not found [{}/{}] returning None.".format(s3_bucket_name_, s3_object_key_))

        return None


def create_zip_file_from_bytes(zip_file_bytes_, mode_="r"):
    """
    Convert Bytes to ZipFile

    :param zip_file_bytes_:
    :param mode_:

    :return:
    """

    zip_file_bytes_io_ = io.BytesIO(zip_file_bytes_)

    return zipfile.ZipFile(zip_file_bytes_io_, mode=mode_), zip_file_bytes_io_


def convert_zipfile_to_bytes(zip_file_):
    """
    Get
    :param zip_file_:
    :return:
    """

    zip_file_.close()

    return zip_file_.fp.getvalue()


def convert_to_base_deployment(full_deployment_bytes_, glob_patterns_):
    """
    Convert to Base Deployment

    :param full_deployment_bytes_:
    :param glob_patterns_:

    :return:
    """

    tempdir_ = tempfile.mkdtemp()

    try:
        base_deployment_bytes_io = io.BytesIO()
        base_deployment_zipfile_ = zipfile.ZipFile(base_deployment_bytes_io, mode="w")
        full_deployment_zipfile_, full_deployment_bytes_io_ = create_zip_file_from_bytes(full_deployment_bytes_)

        full_deployment_zipfile_.extractall(path=tempdir_)

        filenames_ = []

        for glob_pattern_ in glob_patterns_:
            filenames_.extend(glob.glob(tempdir_ + "/" + glob_pattern_))

        filenames_to_exclude_ = []
        for filename_ in filenames_:
            filenames_to_exclude_.append(filename_.replace(tempdir_ + "/", ""))

        file_infos_ = full_deployment_zipfile_.infolist()
        for file_info_ in file_infos_:

            if matches(file_info_.filename, filenames_to_exclude_):
                continue

            file_content_ = full_deployment_zipfile_.read(file_info_)
            base_deployment_zipfile_.writestr(file_info_, file_content_)

        base_deployment_zipfile_.close()

        return base_deployment_bytes_io.getvalue()

    finally:
        shutil.rmtree(tempdir_)


def matches(filename_, filenames_to_exclude_):
    """
    Matches

    :param filename_:
    :param filenames_to_exclude_:

    :return:
    """

    for filename_to_exclude_ in filenames_to_exclude_:
        if filename_ == filename_to_exclude_:
            return True

    return False


def save_deployment_package(deployment_s3_bucket_name_,
                            deployment_s3_object_key_,
                            deployment_package_bytes_):
    """
    Save New Deployment Package

    :param deployment_s3_bucket_name_:
    :param deployment_s3_object_key_:
    :param deployment_package_bytes_:
    """

    s3_.put_object(Bucket=deployment_s3_bucket_name_,
                   Key=deployment_s3_object_key_,
                   Body=deployment_package_bytes_)


def fast_deploy(request_):
    """
    Fast Deploy

    :param request_:

    :return:
    """

    service_name_ = request_["serviceName"]
    deployment_stage_ = request_["deploymentStage"]
    deployment_s3_bucket_name_ = request_["deploymentS3BucketName"]
    base64_encoded_zip_file_bytes_ = request_["base64EncodedZipFileBytes"]
    glob_patterns_ = request_["globPatterns"]

    # Force the creation of a new deployment package
    force_create_new_base_deployment_package_ = request_["forceCreateNewBaseDeploymentPackage"] \
        if "forceCreateNewBaseDeploymentPackage" in request_ else False

    # Create the new deployment package S3 Object Key Prefix
    new_deployment_prefix_ = create_new_deploy_prefix(service_name_, deployment_stage_)

    # Decode the Update Package Zip file from Base64 to a Byte Array
    update_package_bytes_ = base64.b64decode(base64_encoded_zip_file_bytes_)

    update_package_s3_object_key_ = "%s/%s-%s.zip" % (new_deployment_prefix_,
                                                      service_name_,
                                                      update_package_suffix_)

    # Save the update package to S3
    save_deployment_package(deployment_s3_bucket_name_, update_package_s3_object_key_, update_package_bytes_)

    # Create the update package ZipFile from a bytes array
    update_package_, update_package_bytes_io_ = create_zip_file_from_bytes(update_package_bytes_)

    latest_base_deployment_package_bytes_ = None

    if not force_create_new_base_deployment_package_:
        # If we are not forced to create a new base deployment package. Then first look for an existing one.

        deployment_package_name_ = service_name_ + "-" + base_package_suffix_ + ".zip"

        latest_base_deployment_package_bytes_ = get_latest_deployment_package(deployment_s3_bucket_name_,
                                                                              service_name_,
                                                                              deployment_stage_,
                                                                              deployment_package_name_)

    if latest_base_deployment_package_bytes_ is None:

        # If no base deployment package was found, or we are forced to create a new one. Then create a new one.

        log_.info("No Base Deployment found for [{}-{}]".format(service_name_, deployment_stage_))

        # Get the latest full deployment package from S3
        latest_full_deployment_package_bytes_ = get_latest_deployment_package(deployment_s3_bucket_name_,
                                                                              service_name_,
                                                                              deployment_stage_,
                                                                              service_name_ + ".zip")

        if latest_full_deployment_package_bytes_ is None:
            raise Exception("Could not find any deployments for [%s-%s]" % (service_name_, deployment_stage_))

        # Convert the full deployment package to a base deployment package
        latest_base_deployment_package_bytes_ = convert_to_base_deployment(latest_full_deployment_package_bytes_,
                                                                           glob_patterns_)

        # Create the S3 object key for the new base deployment package
        new_base_deployment_s3_object_key_ = "%s/%s-%s.zip" % (new_deployment_prefix_,
                                                               service_name_,
                                                               base_package_suffix_)

        log_.info("Saving new base deployment package [{}]".format(new_base_deployment_s3_object_key_))

        # Save the new base deployment package to S3
        save_deployment_package(deployment_s3_bucket_name_,
                                new_base_deployment_s3_object_key_,
                                latest_base_deployment_package_bytes_)

    # Create a ZipFile from the latest base deployment package
    new_full_deployment_package_, new_full_deployment_package_bytes_io_ = \
        create_zip_file_from_bytes(latest_base_deployment_package_bytes_, mode_="a")

    # Append all the files from the update package to the new full deployment package
    append_update_package(new_full_deployment_package_, update_package_)

    # Create the S3 Object Key for the new full deployment package
    new_full_deployment_s3_object_key_ = new_deployment_prefix_ + "/" + service_name_ + ".zip"

    log_.info("Saving new full deployment package [{}]".format(new_full_deployment_s3_object_key_))

    # Convert the full deployment package ZipFile to byte array
    new_full_deployment_package_.close()
    new_full_deployment_package_bytes_ = new_full_deployment_package_bytes_io_.getvalue()

    # Save the new deployment package to S3
    save_deployment_package(deployment_s3_bucket_name_,
                            new_full_deployment_s3_object_key_,
                            new_full_deployment_package_bytes_)

    return {
        "s3ObjectKey": new_full_deployment_s3_object_key_
    }


def handle(event_, context_):
    return fast_deploy(event_)
