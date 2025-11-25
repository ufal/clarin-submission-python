# This software is licenced under the BSD 3-Clause licence
# available at https://opensource.org/licenses/BSD-3-Clause
# and described in the LICENCE file in the root of this project

"""
Python 3 application for Submission Upload, using the dspace.py API client library.
"""
import argparse
import os

from rest_client.submission_client import SubmissionClient

# Example system variables needed for authentication and submission upload
# (all of these variables can be overwritten with command line arguments)
# AUTHORIZATION_TOKEN=
# DSPACE_API_ENDPOINT=
# DSPACE_COLLECTION_ID=

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Command-line arguments")
parser.add_argument("filename", help="CSV file name")
parser.add_argument("-t", "--token", help="Authorization token (optional), "
                                "or use the AUTHORIZATION_TOKEN env variable")
parser.add_argument("-e", "--dspace-api-endpoint", help="DSpace API Endpoint (optional), "
                                                        "or use the DSPACE_API_ENDPOINT env variable")
parser.add_argument("-c", "--collection-id", help="DSpace Collection ID (optional), "
                                                  "or use the DSPACE_COLLECTION_ID env variable")
args = parser.parse_args()

AUTHORIZATION_TOKEN = None
if args.token:
    AUTHORIZATION_TOKEN = args.token
elif 'AUTHORIZATION_TOKEN' in os.environ:
    AUTHORIZATION_TOKEN = os.environ['AUTHORIZATION_TOKEN']

if AUTHORIZATION_TOKEN is None:
    print('No authorization token provided!')
    exit(1)

API_ENDPOINT = 'http://localhost:8080/server/api'
if args.dspace_api_endpoint:
    API_ENDPOINT = args.dspace_api_endpoint
elif 'DSPACE_API_ENDPOINT' in os.environ:
    API_ENDPOINT = os.environ['DSPACE_API_ENDPOINT']

DSPACE_COLLECTION_ID = None
if args.collection_id:
    DSPACE_COLLECTION_ID  = args.collection_id
elif 'DSPACE_COLLECTION_ID' in os.environ:
    DSPACE_COLLECTION_ID = os.environ['DSPACE_COLLECTION_ID']

if DSPACE_COLLECTION_ID is None:
    print('No DSpace collection id provided!')
    exit(1)

FILE_TYPE = 'csv'

d = SubmissionClient(api_endpoint=API_ENDPOINT, authorization_token=AUTHORIZATION_TOKEN)

# Authenticate against the DSpace client
authenticated = d.authenticate()
if not authenticated:
    print('Error logging in! Giving up.')
    exit(1)

# for now, only CSV files are supported
if FILE_TYPE == 'csv':
    submissionResponse = d.create_submission_from_csv(DSPACE_COLLECTION_ID, args.filename)
    if submissionResponse is not None:
        if submissionResponse.status_code == 201:
            print(f'Submission \"{submissionResponse.json()["_embedded"]["item"]["name"]}\" '
                  f'with id {submissionResponse.json()["id"]} created successfully.')
        else:
            print(f'Submission creation failed with status code {submissionResponse.status_code}')
            if submissionResponse.request and submissionResponse.request.method:
                print(f'Method: {submissionResponse.request.method}')
            if submissionResponse.url:
                print(f'Request URL: {submissionResponse.url}')
            if submissionResponse.text:
                print(f'Reason: {submissionResponse.text}')