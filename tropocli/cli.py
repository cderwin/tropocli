import batch
import boto3
from botocore.exceptions import ClientError
from common import project_name
import click
import hashlib
import inference
import json


capabilities = ['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM', 'CAPABILITY_AUTO_EXPAND']
templates = {
    'batch': batch.t,
    'inference': inference.t,
}


def get_hash(obj):
    h = hashlib.sha256()
    if isinstance(obj, dict):
        obj = json.dumps(obj, sort_keys=True).encode()

    h.update(obj)
    return h.hexdigest()[:8]


def stack_exists(ctx, stack_name):
    try:
        response = ctx.obj['cloudformation'].describe_stacks(StackName=stack_name)
        return response['Stacks'][0]['StackStatus'] != 'REVIEW_IN_PROGRESS'
    except ClientError:
        return False


def get_stack_name(template_name):
    return project_name + '-stack-' + template_name


@click.group()
@click.option('--profile', default=None, type=str, help='profile to use for interaction with aws (stack creation/deletiong; template validation)')
@click.option('--template', default=None, multiple=True, type=str, help=f"template to use; may be provided multiple times but must be a subset of [{', '.join(templates.keys())}]")
@click.pass_context
def cli(ctx, profile, template):
    if not template:
        template = templates.keys()

    template_map = {}
    for template_name in template:
        if template_name not in templates.keys():
            raise ValueError('Invalid template name')

        template_map[template_name] = templates[template_name]

    ctx.ensure_object(dict)
    ctx.obj['templates'] = template_map
    ctx.obj['cloudformation'] = boto3.Session(profile_name=profile).client('cloudformation')


@cli.command()
@click.option('--format', default='yaml', type=click.Choice(['json', 'yaml']), help='output format for templates')
@click.pass_context
def render(ctx, format):
    for template_name, template in ctx.obj['templates'].items():
        with open(f"{template_name}.{format}", 'w') as fh:
            output = template.to_json() if format == 'json' else template.to_yaml()
            fh.write(output)


@cli.command()
@click.pass_context
def validate(ctx):
    for i, (template_name, template) in enumerate(ctx.obj['templates'].items()):
        template_body = template.to_json()
        response = ctx.obj['cloudformation'].validate_template(TemplateBody=template_body)

        click.echo(f"Template: {template_name}")
        click.echo("--------------------------")
        click.echo("Valid: True")
        click.echo(f"Required Capabilities: {response['Capabilities']}")
        click.echo(f"Capabilities Reason: {response['CapabilitiesReason']}")

        if i + 1 < len(ctx.obj['templates']):
            click.echo('\n')


def get_stack_args(stack_name, template, raw_params, capabilities, raw_tags):
    tags = []
    for tag_str in raw_tags:
        try:
            key, value = tag_str.split('=', 1)
        except ValueError:
            raise ValueError(f'Malformatted tag string: `{tag_str}`')

        tags.append({
            'Key': key,
            'Value': value,
        })

    params = []
    for param_str in raw_params:
        try:
            key, value = param_str.split('=', 1)
        except ValueError:
            raise ValueError('Malformed parameter string: `{param_str}`')

        params.append({
            'ParameterKey': key,
            'ParameterValue': value,
        })

    return {
        'StackName': stack_name,
        'TemplateBody': template.to_json(),
        'Parameters': params,
        'Capabilities': capabilities,
        'Tags': tags,
    }


@cli.command()
@click.option('--tag', '-t', default=None, type=str, multiple=True, help='Tags to use for the stack; these tags will be propagated to onfrastructure when possible')
@click.option('--param', '-p', default=None, type=str, multiple=True, help='Template parameters to be overriden for stack creation; parameters must apply to all templates used')
@click.option('--capability', '-c', default=None, type=click.Choice(capabilities), multiple=True, help='Capability required to create changeset')
@click.pass_context
def preview(ctx, tag, param, capability):
    for i, (template_name, template) in enumerate(ctx.obj['templates'].items()):
        click.echo('Creating change set...')
        stack_name = get_stack_name(template_name)
        change_set_args = get_stack_args(stack_name, template, param, capability, tag)
        change_set_args['ChangeSetName'] = '-'.join([stack_name, get_hash(change_set_args), 'change-set'])
        change_set_args['ChangeSetType'] = 'UPDATE' if stack_exists(ctx, stack_name) else 'CREATE'
        create_response = ctx.obj['cloudformation'].create_change_set(**change_set_args)

        click.echo('Fetching change set...')
        response = ctx.obj['cloudformation'].describe_change_set(ChangeSetName=create_response['Id'])
        click.echo(f"Change set id: {response['ChangeSetId']}")
        click.echo()
        for change in response['Changes']:
            change = change['ResourceChange']
            action = change['Action']
            id = change['LogicalResourceId'] + ' (' + change['PhysicalResourceId'] + ')' if 'PhysicalResourceId' in change else change['LogicalResourceId']
            resource_type = change['ResourceType']
            scopes = 'at scope(s) [' + ', '.join(change['Scope']) + ']' if change['Scope'] else ''
            replace_str = 'without replacement' if response.get('Replacement') == 'False' else 'with replacement'
            click.echo(f"Change: {action} resource {id} of type {resource_type} {scopes} {replace_str}")
        
        click.echo()
        click.echo(f"To execute this changeset, run `python3 cloudformation/cli.py apply --changeset {response['ChangeSetId']}`")

        if i + 1 < len(ctx.obj['templates']):
            click.echo('\n')


@cli.command()
@click.option('--changeset', default=None, type=str, help='apply this changeset instead of directly updating')
@click.option('--tag', '-t', default=None, type=str, multiple=True, help='Tags to use for the stack; these tags will be propagated to onfrastructure when possible')
@click.option('--param', '-p', default=None, type=str, multiple=True, help='Template parameters to be overriden for stack creation')
@click.option('--capability', '-c', default=None, type=click.Choice(capabilities), multiple=True, help='Capability required to create changeset')
@click.pass_context
def apply(ctx, changeset, tag, param, capability):
    if changeset is not None:
        if tag:
            raise ValueError('Tags cannot be given with changeset')

        if param:
            raise ValueError('Parametes cannot be given with changeset')

        if capability:
            raise ValueError('Capabilities cannot be given with changeset')

        ctx.obj['cloudformation'].execute_change_set(ChangeSetName=changeset)
        click.echo('Change set has been executed.')
        return

    for i, (template_name, template) in enumerate(ctx.obj['templates'].items()):
        click.echo('Creating change set...')
        stack_name = get_stack_name(template_name)
        stack_args = get_stack_args(stack_name, template, param, capability, tag)
        if stack_exists(ctx, stack_name):
            click.echo(f'Updating stack `{stack_name}`...')
            ctx.obj['cloudformation'].update_stack(**stack_args)
            click.echo('Stack updated.')
            return

        click.echo(f'Creating stack `{stack_name}`...')
        ctx.obj['cloudformation'].create_stack(**stack_args)
        click.echo('Stack created.')

        if i + 1 < len(ctx.obj['templates']):
            click.echo('\n')


@cli.command()
@click.pass_context
def status(ctx):
    for i, (template_name, _) in enumerate(ctx.obj['templates'].items()):
        stack_name = get_stack_name(template_name)
        try:
            response = ctx.obj['cloudformation'].describe_stacks(StackName=stack_name)
            exists = True
        except ClientError:
            click.echo(f'Stack `{stack_name}` does not exist.')
            exists = False

        if exists:
            stack_data = response['Stacks'][0]
            click.echo('Stack name: ' + stack_data['StackName'])
            click.echo('Stack arn: ' + stack_data['StackId'])

            if 'Description' in stack_data:
                click.echo('Description: ' + stack_data['Description'])

            click.echo('Status: ' + stack_data['StackStatus'])
            if 'LastUpdatedTime' in stack_data:
                click.echo('Last updated at: ' + str(stack_data['LastUpdatedTime']))

            click.echo('Created at: ' + str(stack_data['CreationTime']))
            if 'Outputs' in stack_data:
                click.echo('Outputs:')
                for output in stack_data['Outputs']:
                    key = output['OutputKey']
                    value = output['OutputValue']
                    click.echo(f'\t{key} = {value}')

        if i + 1 < len(ctx.obj['templates']):
            click.echo()


@cli.command()
@click.option('--retain', '-r', default=[], type=str, multiple=True, help='Resource physical ids to retain')
@click.pass_context
def delete(ctx, retain):
    if len(ctx.obj['templates']) > 1:
        raise ValueError('Delete one stack at a time.')

    for template_name, _ in ctx.obj['templates'].items():
        stack_name = get_stack_name(template_name)
        click.echo(f'Deleting stack `{stack_name}`...')
        ctx.obj['cloudformation'].delete_stack(StackName=stack_name, RetainResources=retain)
        click.echo(f'Stack `{stack_name}` deleted.')


if __name__ == '__main__':
    cli()
