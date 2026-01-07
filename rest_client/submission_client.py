from dspace_rest_client.client import DSpaceClient
from enum import Enum
import logging
import csv
import os
import json
from requests import Request
from requests import Response

__all__ = ['SubmissionClient', 'handle_failed_response', 'parse_submission_payload_csv']

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
_logger = logging.getLogger('clarin.dspace')

API_ENDPOINT = ''
AUTHORIZATION_TOKEN = ''

class PatchOperation(Enum):
    ADD = 'add'
    REMOVE = 'remove'
    REPLACE = 'replace'
    MOVE = 'move'

def handle_failed_response(operation_name, response: Response):
    print(f"{operation_name} failed with status code {response.status_code}")
    if response.request and response.request.method:
        print(f"Method: {response.request.method}")
    if response.url:
        print(f"Request URL: {response.url}")
    if response.text:
        print(f"Reason: {response.text}")


def parse_submission_payload_csv(file_path):
    operations = []
    with open(file_path, 'r') as file:
        reader = csv.reader(file)
        section_path = ''
        operation_map = {}
        for row in reader:
            if len(row) == 0:
                print('')
                continue
            print(row)
            if row[0] == '__section__':
                section_path = '/sections/' + row[1]
            elif len(row) > 1 and row[1] is not None and row[1] != '':
                metadata_key = row[0].split("[")[0]
                path = section_path + '/' + metadata_key
                if path == "/sections/license/granted":
                    # special handling for license granted field
                    operation = {
                        'op': 'add',
                        'path': path,
                        'value': row[1]
                    }
                    operation_map[path] = operation
                    continue
                if path == "/sections/clarin-license/__enum_value__":
                    # special handling for clarin-license enum value
                    continue
                if path == "/sections/clarin-license/name":
                    # special handling for clarin-license
                    operation = {
                        'op': 'replace',
                        'path': '/license',
                        'value': row[1]
                    }
                    operation_map["/license"] = operation
                    continue
                if operation_map.get(path) is None:
                    value = []
                    for num in range(1, len(row)):
                        value.append({
                            'value': row[num]
                        })
                    operation = {
                        'op': 'add',
                        'path': path,
                        'value': value
                    }
                    operation_map[path] = operation
                else:
                    operation = operation_map.get(path)
                    for num in range(1, len(row)):
                        operation['value'].append({
                            'value': row[num]
                        })

        for key in operation_map:
            operations.append(operation_map[key])
    return operations

class SubmissionClient:
    def __init__(self, api_endpoint = API_ENDPOINT, authorization_token = AUTHORIZATION_TOKEN):
        self.authorization_token = authorization_token
        self.api_endpoint = api_endpoint
        self.dspaceClient = DSpaceClient(api_endpoint=self.api_endpoint, username = 'CLARIN_DSPACE_USER')
        self.dspaceClient.auth_request_headers["Authorization"] = "Bearer " + self.authorization_token
        self.valid_operations = [member.value for member in PatchOperation]

    def authenticate(self, retry=False):
        if self.authorization_token == '':
            print('No authorization token provided!')
            return False
        return self.dspaceClient.authenticate()

    def create_submission(self, parent):
        url = f'{self.api_endpoint}/submission/workspaceitems'
        if not parent:
            _logger.error('Need a parent UUID!')
            return None
        params = {'owningCollection': parent}

        r = self.dspaceClient.api_post(url, params, None)
        if r.status_code == 201:
            # 201 Created - success!
            _logger.info(f'New submission with id {r.json()["id"]} created successfully!')
        else:
            _logger.error(f'create operation failed: {r.status_code}: {r.text} ({url})')
        return r

    def create_submission_from_csv(self, parent, csv_file_path):
        payload = parse_submission_payload_csv(csv_file_path)
        return self._create_submission_from_payload(parent, payload)

    def _create_submission_from_payload(self, parent, payload):
        create_response = self.create_submission(parent)
        if create_response.status_code == 201:
            workspace_item_id = create_response.json()['id']
            patch_response =  self.patch_metadata(workspace_item_id, payload)
            if patch_response is not None and patch_response.status_code == 200:
                patch_response.status_code = 201
                return patch_response

        return create_response

    def patch_metadata(self, workspace_item_id, data):
        url = f'{self.api_endpoint}/submission/workspaceitems/{workspace_item_id}'
        if not data:
            _logger.error('No data provided for patch operation!')
            return None
        if data.__class__ != list or len(data) == 0:
            _logger.error('Input data should be in the form of the list of operations')
            return None

        print("Patch operations:")
        for operation in data:
            print(operation)
            path = operation['path'] if 'path' in operation else None
            if not path:
                _logger.error('Need valid path eg. /withdrawn or /metadata/dc.title/0')
                return None
            op = operation['op'] if 'op' in operation else None
            value = operation['value'] if 'value' in operation else None
            if op not in self.valid_operations:
                _logger.error('Invalid operation name: {}'.format(op))
                return None
            if value is None and op != PatchOperation.REMOVE.value:
                # missing value required for add/replace/move operations
                _logger.error('Missing required "value" argument for add/replace/move operations')
                return None
            if op == PatchOperation.REPLACE.value and path != '/license' and not isinstance(value, dict):
                # value should be object in replace operation
                _logger.error('Invalid value format for replace operation - should be object')
                return None
            if op == PatchOperation.ADD.value and data.__class__ != list:
                # value should be list in add operation
                _logger.error('Invalid value format for add operation - should be list')
                return None

        # perform patch request
        r = self.dspaceClient.session.patch(url, json = data, headers=self.dspaceClient.request_headers)
        self.dspaceClient.update_token(r)

        if r.status_code == 200:
            # 200 Success
            _logger.info(f'Successful patch update to {r.json()["type"]} {r.json()["id"]}')
        else:
            _logger.error(r.text)
        # Return the raw API response
        return r

    def generate_csv_template(self, csv_file_name, submission_definition_name, resource_type):
        submission_form_names = self._get_submission_form_names(submission_definition_name)
        if submission_form_names is not None and len(submission_form_names) > 0:
            csv_lines = []
            first_section = True
            for form_name in submission_form_names:
                url = f'{self.api_endpoint}/config/submissionforms/{form_name}'
                r = self.dspaceClient.session.get(url, headers=self.dspaceClient.request_headers)
                if r is not None and r.status_code == 200:
                    _logger.info(f'successful retrieval of submission form {form_name}')
                    rows = r.json().get('rows', [])
                    if len(rows) > 0:
                        if not first_section:
                            csv_lines.append([])  # add an empty line between sections
                        else:
                            first_section = False

                        csv_lines.append(['__section__', form_name])
                        for row in rows:
                            fields = row.get('fields', [])
                            if len(fields) > 0:
                                for field in fields:
                                    type_bind = field.get("typeBind", [])
                                    # check if the resource_type is in the typeBind list
                                    if len(type_bind) == 0 or resource_type in type_bind:
                                        selectable_metadata = field.get("selectableMetadata", [])
                                        if len(selectable_metadata) > 0:
                                            metadata_key = selectable_metadata[0].get("metadata")
                                            controlled_vocabulary = field.get("selectableMetadata")[0].get("controlledVocabulary", "")
                                            value_format = self._get_format(field, controlled_vocabulary )
                                            if metadata_key is not None:
                                                if metadata_key == 'dc.type': # special handling for dc.type field
                                                    csv_lines.append([metadata_key + value_format, resource_type])
                                                else:
                                                    csv_lines.append([metadata_key + value_format, ''])

            csv_lines.append([]) # empty line
            csv_lines.append(['__section__', 'license'])
            csv_lines.append(['granted[required=true type=enum(true|false)]', 'true'])

            clarin_licenses = self._get_clarin_licenses()
            if len(clarin_licenses) > 0:
                csv_lines.append([]) # empty line
                csv_lines.append(['__section__', 'clarin-license'])
                for clarin_license in clarin_licenses:
                    csv_lines.append(['__enum_value__', clarin_license])
                # populate clarin-license name with the first license as default
                csv_lines.append(['name[type=enum]', clarin_licenses[0]])

            if len(csv_lines) > 0:
                with open(csv_file_name, 'w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerows(csv_lines)

            _logger.info(f'CSV template for submission definition: "{submission_definition_name}" '
                         f'written to: "{csv_file_name}"')
        else:
            _logger.error(f'No submission forms found for submission definition name: "{submission_definition_name}"')

    def _get_submission_form_names(self, submission_definition_id):
        url = f'{self.api_endpoint}/config/submissiondefinitions/{submission_definition_id}?embed=sections'
        r = self.dspaceClient.session.get(url, headers=self.dspaceClient.request_headers)
        if r is not None and r.status_code == 200:
            _logger.info(f'successful retrieval of submission definition {submission_definition_id}')
            form_names = []
            sections = r.json().get('_embedded', {}).get('sections', {}).get('_embedded', {}).get('sections', [])
            for section in sections:
                if section.get('sectionType') == 'submission-form':
                    form_names.append(section.get('id'))
            return form_names

        return None

    def upload_file_to_workspace_item(self, workspace_item_id, file_paths):
        url = f'{self.api_endpoint}/submission/workspaceitems/{workspace_item_id}'
        for file_path in file_paths:
            # the API only allows to upload one file per request
            file = (os.path.basename(file_path), open(file_path, 'rb'))
            req = Request('POST', url, files = {'file': file})
            prepared_req = self.dspaceClient.session.prepare_request(req)
            r = self.dspaceClient.session.send(prepared_req)
            if r.status_code == 201:
                # 201 Created - success!
                print(f'File "{file_path}" uploaded successfully to workspace item {workspace_item_id}')
            else:
                print(f'File upload for "{file_path}" failed: {r.status_code}: {r.text} ({url})')

    def _get_format(self, field, controlled_vocabulary):
        format = "["

        required = field.get("mandatory", False)
        if required:
            format += "required=true"

        repeatable = field.get("repeatable", False)
        if repeatable:
            if required:
                format += " "
            format += "repeatable=true"

        input_type = field.get("input", {}).get("type")

        if "date" == input_type:
            if required:
                format += " "
            format += "type=date format=<dddd-mm-dd>"

        elif "complex" == input_type:
            json_array = json.loads(field.get("complexDefinition", "[]"))

            if (len (json_array) > 0):
                if required or repeatable:
                    format += " "
                format += "type=complex format=<"
                first = True
                for item in json_array:
                    for key in item.keys():
                        if not item.get(key).get("readonly"):
                            # add field separator
                            if first:
                                first = False
                            else:
                                format += ";"
                            # add field name
                            field_name = item.get(key).get("name")
                            format += field_name
                            # add field type
                            field_type = item.get(key).get("input-type", "text")
                            if field_type == "text" or field_type == "autocomplete":
                                format += ":text"
                            if field_type == "dropdown":
                                cv = item.get(key).get("value-pairs-name")
                                if cv is not None:
                                    values = self._get_vocabulary_values(cv)
                                    if len(values) > 0:
                                        format += ":enum(" + "|".join(values) + ")"

                format += ">"
        elif "dropdown" == input_type or "list" == input_type:
            if controlled_vocabulary is not None:
                values = self._get_vocabulary_values(controlled_vocabulary)
                if len(values) > 0:
                    if required or repeatable:
                        format += " "
                    format += "type=enum(" + "|".join(values) + ")"
        else:
            regex = field.get("input", {}).get("regex", "")
            if regex.startswith("http"):
                if required or repeatable:
                    format += " "
                format+= "type=URL"

        format += "]"

        return format

    def _get_vocabulary_values(self, vocabulary_name):
        values = []
        url = f'{self.api_endpoint}/submission/vocabularies/{vocabulary_name}/entries'
        r = self.dspaceClient.session.get(url, headers=self.dspaceClient.request_headers)
        if r is not None and r.status_code == 200:
            entries = r.json().get('_embedded', {}).get('entries', [])
            for entry in entries:
                value = entry.get('value')
                if value is not None and len(value) > 0:
                    values.append(value)
        return values

    def _get_clarin_licenses(self):
        values = []
        url = f'{self.api_endpoint}/core/clarinlicenses?size=1000'
        r = self.dspaceClient.session.get(url, headers=self.dspaceClient.request_headers)
        if r is not None and r.status_code == 200:
            entries = r.json().get('_embedded', {}).get('clarinlicenses', [])
            for entry in entries:
                value = entry.get('name')
                if value is not None and len(value) > 0:
                    values.append(value)
        return values
