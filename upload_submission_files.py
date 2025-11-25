# This software is licenced under the BSD 3-Clause licence
# available at https://opensource.org/licenses/BSD-3-Clause
# and described in the LICENCE file in the root of this project

"""
Python 3 application for uploading submission files, using the dspace.py API client library.
"""
import argparse
import os

from rest_client.submission_client import SubmissionClient

# Example system variables needed for authentication and submission files upload
# (all of these variables can be overwritten with command line arguments)
# AUTHORIZATION_TOKEN=
# DSPACE_API_ENDPOINT=

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Command-line arguments")
parser.add_argument("-s", "--submission-id", required = True, help="submission ID (required)")
parser.add_argument("-f", "--files", nargs="+", required = True, help="Files to upload (required")
parser.add_argument("-t", "--token",
                    help="Authorization token (optional), r use the AUTHORIZATION_TOKEN env variable")
parser.add_argument("-e", "--dspace-api-endpoint",
                    help="DSpace API Endpoint (optional), or use the DSPACE_API_ENDPOINT env variable")
args = parser.parse_args()

SUBMISSION_ID = args.submission_id
FILES = args.files

if SUBMISSION_ID is None:
    print('No submission-id parameter provided!')
    exit(1)

if FILES is None:
    print('No files parameter provided!')
    exit(1)

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

d = SubmissionClient(api_endpoint=API_ENDPOINT, authorization_token=AUTHORIZATION_TOKEN)

# Authenticate against the DSpace client
authenticated = d.authenticate()
if not authenticated:
    print('Error logging in! Giving up.')
    exit(1)

d.upload_file_to_workspace_item(SUBMISSION_ID, FILES)