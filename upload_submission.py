# This software is licenced under the BSD 3-Clause licence
# available at https://opensource.org/licenses/BSD-3-Clause
# and described in the LICENCE file in the root of this project

"""
Python 3 application for Submission Upload, using the dspace.py API client library.
"""
import argparse
import os

from rest_client.submission_client import SubmissionClient, handle_failed_response, parse_submission_payload_csv

# Example system variables needed for authentication and submission upload
# (all of these variables can be overwritten with command line arguments)
# AUTHORIZATION_TOKEN=
# DSPACE_API_ENDPOINT=
# DSPACE_COLLECTION_ID=

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Command-line arguments")
parser.add_argument("-m", "--submission-metadata",
                    help="Submission metadata file name, in CSV format (optional). Default: submission.csv")
parser.add_argument("-s", "--submission-id", help="submission ID (optional),"
                                                  " if provided, metadata + files will be uploaded to this submission")
parser.add_argument("-f", "--files", nargs="+", help="Files to upload (optional)")
parser.add_argument("-t", "--token",
                    help="Authorization token, or use the AUTHORIZATION_TOKEN env variable")
parser.add_argument("-e", "--dspace-api-endpoint",
                    help="DSpace API, or use the DSPACE_API_ENDPOINT env variable")
parser.add_argument("-c", "--collection-id",
                    help="DSpace Collection ID, or use the DSPACE_COLLECTION_ID env variable")
args = parser.parse_args()

SUBMISSION_METADATA = 'submission.csv'
if args.submission_metadata:
    SUBMISSION_METADATA = args.submission_metadata

FILES = args.files or []
SUBMISSION_ID = args.submission_id

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
    if not SUBMISSION_ID:
        submission_response = d.create_submission_from_csv(DSPACE_COLLECTION_ID, SUBMISSION_METADATA)
        if submission_response is not None:
            if submission_response.status_code == 201:
                submission_id = submission_response.json()['id']
                submission_name = submission_response.json()['_embedded']['item']['name'] or "Untitled"
                print(f'Submission \"{submission_name}\" with id {submission_id} created successfully.')
                if len(FILES) > 0:
                    d.upload_file_to_workspace_item(submission_id, FILES)
            else:
                handle_failed_response("Submission create", submission_response)
    else:
        payload = parse_submission_payload_csv(SUBMISSION_METADATA)
        if len(payload) > 0:
            submission_response = d.patch_metadata(SUBMISSION_ID, payload)
            if submission_response is not None:
                if submission_response.status_code == 200:
                    submission_name = submission_response.json()['_embedded']['item']['name'] or "Untitled"
                    print(f'Submission \"{submission_name}\" with id {SUBMISSION_ID} updated successfully.')
                else:
                    handle_failed_response("Submission update", submission_response)
        else:
            print("No metadata found in csv file.")
        if len(FILES) > 0:
            d.upload_file_to_workspace_item(SUBMISSION_ID, FILES)