#!/usr/bin/env python3

import logging
from datetime import datetime, timezone, timedelta
import boto3
import signal
import botocore
import nartool
import sys
import os

errors = 0

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

NIX_CACHE_PUBLIC_KEY_NAMES = os.environ.get("NIX_CACHE_PUBLIC_KEY_NAMES", "").split()
NIX_CACHE_S3_BUCKET_NAME = os.environ["NIX_CACHE_S3_BUCKET_NAME"]
NIX_CACHE_RETENTION_DAYS = os.environ["NIX_CACHE_RETENTION_DAYS"]

def delete_object(obj, reason=None):
    logger.info(f"Dropping {obj.key}. Reason: {reason}")
    if is_narinfo(obj):
        narinfo = get_narinfo(obj)
        logger.info(f"Dropping {narinfo.StorePath}. Reason: Part of {obj.key}")
        obj.Bucket().Object(narinfo.URL).delete()
    obj.delete()

def get_narinfo(obj) -> nartool.store.NarInfo:
    body = obj.get()["Body"].read().decode()
    return nartool.store.NarInfo(body)

def is_narinfo(obj) -> bool:
    return obj.key.endswith(".narinfo")

def signal_handler(sig, frame):
    print("Aborting.")
    exit(1)
    
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    if not NIX_CACHE_PUBLIC_KEY_NAMES:
        logger.warning("Not checking public keys as NIX_CACHE_PUBLIC_KEYS is not set")

    cutoff = datetime.now(timezone.utc) - timedelta(days=int(NIX_CACHE_RETENTION_DAYS))

    s3_resource = boto3.resource('s3')
    bucket = s3_resource.Bucket(NIX_CACHE_S3_BUCKET_NAME)
    dropped = 0
    for i, obj in enumerate(bucket.objects.all(), start=1):
        try:
            if obj.last_modified < cutoff:
                delete_object(obj, reason=f"Older than retention time. Last modified {obj.last_modified}")
                dropped += 1
            elif is_narinfo(obj) and NIX_CACHE_PUBLIC_KEY_NAMES:
                narinfo = get_narinfo(obj)
                key_names = [sig.split(":")[0] for sig in narinfo.Sig]
                if not (set(NIX_CACHE_PUBLIC_KEY_NAMES) & set(key_names)):
                    delete_object(obj, reason=f"No accepted key. Keys: {key_names}")
                    dropped += 1
        except botocore.exceptions.ClientError:
            logger.warning(f"Could not access {obj.key}. Skipping.")
    
        if i % 100 == 0:
            logger.info(f"Dropped {dropped}/{i} objects")
    else:
        logger.info("Done.")
        logger.info(f"Dropped {dropped}/{i} objects")
        
