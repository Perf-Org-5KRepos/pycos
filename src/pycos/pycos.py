"""Simplified cloud object store api wrapper
/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * The ASF licenses this file to You under the Apache License, Version 2.0
 * (the "License"); you may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
"""

import logging
import os
import os.path
import tempfile
import warnings

import requests
import ibm_boto3
from ibm_botocore.client import Config
from ibm_botocore.client import ClientError

LOGGER = logging.getLogger('PYCOS')
LOGGER.setLevel(logging.CRITICAL)

warnings.filterwarnings("ignore", category=DeprecationWarning)


COSClientError = ClientError


class COS:
    '''COS

    '''
    def __init__(self, config, endpoint=None):
        cfg = Config(signature_version='s3v4')

        hmac_key = config['cos_hmac_keys']['access_key_id']
        hmac_secret = config['cos_hmac_keys']['secret_access_key']
        if endpoint is None:
            endpoint = config['endpoint']

        self.config = config
        self.cos = ibm_boto3.client(
            's3',
            aws_access_key_id=hmac_key,
            aws_secret_access_key=hmac_secret,
            endpoint_url=endpoint,
            config=cfg)

    @staticmethod
    def url_from_location(config, location, url_type='public'):
        '''url_from_location

        '''
        if url_type.lower() not in ('public', 'private', 'direct'):
            return None

        rsp = requests.get(config['endpoints'])
        jsn = rsp.json()

        url = jsn['service-endpoints']['regional'][location][url_type][location]
        url = 'https://' + url

        return url


class COSAdmin(COS):
    '''COSAdmin

    '''
    def bucket_create(self, name, acl='private'):
        '''bucket create

        '''
        self.cos.create_bucket(ACL=acl, Bucket=name)

    def bucket_list(self):
        '''bucket list

        '''
        rsp = self.cos.list_buckets_extended()

        if 'Buckets' in rsp.keys():
            return rsp['Buckets']

        return []

    def bucket_contents(self, name, max_keys=100):
        '''bucket contents

        '''
        more_results = True
        next_token = ""

        files = []
        while more_results:
            response = self.cos.list_objects_v2(
                Bucket=name,
                MaxKeys=max_keys,
                ContinuationToken=next_token)

            batch = response["Contents"]
            files += batch

            if response["IsTruncated"]:
                next_token = response["NextContinuationToken"]
            else:
                more_results = False
                next_token = ""

        return files

    def bucket_content_delete(self, name, key):
        '''bucket content delete

        '''
        self.cos.delete_object(Bucket=name, Key=key)

    def bucket_delete(self, name):
        '''delete bucket

        '''
        self.cos.delete_bucket(Bucket=name)


class COSReader(COS):
    '''COSReader

    '''
    def __enter__(self):
        self.cos.download_file(self.bucket, self.key, self.tmp)
        self.open_file = open(self.tmp)

        return self.open_file

    def __exit__(self, except_type, except_value, traceback):
        self.open_file.close()
        os.remove(self.tmp)

    def __init__(self, config, bucket, key):
        self.bucket = bucket
        self.key = key
        self.open_file = None
        self.tmp = os.path.join(tempfile.mkdtemp(), key)

        super().__init__(config)


class COSWriter(COS):
    '''COSWriter

    '''
    def __init__(self, config, bucket):
        self.bucket = bucket

        super().__init__(config)

    def store(self, key, data):
        '''store

        '''
        self.cos.put_object(Bucket=self.bucket, Key=key, Body=data)

    def upload(self, key, filename, extra_args=None, callback=None, config=None):
        '''upload

        '''
        self.cos.upload_file(
            filename,
            self.bucket,
            key,
            ExtraArgs=extra_args,
            Callback=callback,
            Config=config)


class COSPresignedURL():
    '''COSPresignedURL

    '''
    def __init__(self, hmac_key, hmac_secret, endpoint):
        cfg = Config(signature_version='s3v4')
        self.cos = ibm_boto3.client(
            's3',
            aws_access_key_id=hmac_key,
            aws_secret_access_key=hmac_secret,
            endpoint_url=endpoint,
            config=cfg)

    def create_post(self, bucket, key, expires_in=300):
        '''create_post

        '''
        return self.cos.generate_presigned_post(bucket, key, ExpiresIn=expires_in)

    def create_get(self, bucket, key, expires_in=300):
        '''create_get

        '''
        params = {'Bucket':bucket, 'Key': key}
        return self.cos.generate_presigned_url('get_object', Params=params, ExpiresIn=expires_in)
