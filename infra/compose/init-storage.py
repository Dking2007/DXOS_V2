# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Provision the private development bucket before Core readiness checks."""

from __future__ import annotations

import os
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ConnectionClosedError, EndpointConnectionError

client = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_ENDPOINT"],
    aws_access_key_id=os.environ["S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["S3_SECRET_KEY"],
    region_name="us-east-1",
    config=Config(signature_version="s3v4", connect_timeout=3, read_timeout=5, retries={"max_attempts": 1}),
)
bucket = os.environ.get("S3_BUCKET", "dx-files")
for attempt in range(60):
    try:
        try:
            client.head_bucket(Bucket=bucket)
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 404:
                raise
            client.create_bucket(Bucket=bucket)
        # A new S3 bucket is private. No public policy or anonymous ACL is installed.
        print(f"Private bucket {bucket} ready")
        break
    except (EndpointConnectionError, ConnectionClosedError):
        if attempt == 59:
            raise
        time.sleep(2)
else:
    raise RuntimeError("Object storage did not become ready")
