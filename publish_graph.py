import boto3
import click
import os
import paramiko
import select
import time


def exec_command(command, client):
    """ execute a command at a remote SSH server

    :param str command: command to execute
    :param SSHClient client: session at the SSH server

    """
    print 'Command: {cmd}'.format(cmd=command)
    stdin, stdout, stderr = client.exec_command(command)
    while not stdout.channel.exit_status_ready():
        if stdout.channel.recv_ready():
            rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
            if len(rl) > 0:
                # Print data from stdout
                print stdout.channel.recv(1024)


def push_to_instance(instance_id, ssh_user, ssh_private_key, base_source_path, base_destination_path, routers):
    private_key = paramiko.RSAKey.from_private_key_file(ssh_private_key)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print 'Connecting to the EC2 instance with IP Addresses {ip}'.format(ip=instance_id)
    client.connect(hostname=instance_id, username=ssh_user, pkey=private_key)
    try:
        # stop otp service (via supervisor)
        exec_command('sudo supervisorctl stop otp', client)

        for router in routers:
            graph_source_path = os.path.join(base_source_path, router, 'Graph.obj')
            graph_destination_path = os.path.join(base_destination_path, router, 'Graph.obj')

            print "Uploading {file} to {instance}".format(file=graph_source_path, instance=instance_id)
            with client.open_sftp() as sftp:
                sftp.put(graph_source_path, '/tmp/{router}_graph.obj'.format(router=router))

            exec_command('sudo chown otp:otp /tmp/{router}_graph.obj'.format(router=router), client)
            exec_command('sudo mv {dest_path} /tmp/{router}_graph.obj.tmp'.format(
                dest_path=graph_destination_path, router=router), client)
            exec_command('sudo mv /tmp/{router}_graph.obj {dest_path}'.format(
                router=router, dest_path=graph_destination_path), client)

        # start otp service again after Graph files were updated
        exec_command('sudo supervisorctl start otp')

        # suspending the execution for 5 minutes, until Graph has been indexed and Grizzly server be running
        print "Waiting until Graph has been indexed and Grizzly server is running again"
        time.sleep(360)
    except Exception, ex:
        print ex
    finally:
        client.close()


@click.command()
@click.option('--elb_name', prompt='ELB name to look for instances')
@click.option('--aws_access_key_id', default=None)
@click.option('--aws_secret_access_key', default=None)
@click.option('--aws_region_name', default='us-west-2')
@click.option('--aws_profile_name', default=None)
@click.option('--ssh_user', default='ubuntu')
@click.option('--ssh_private_key', prompt='Private Key File to connect to EC2 instances')
@click.option('--base_source_path', prompt='Base Source Path')
@click.option('--base_destination_path', prompt='Base Destination Path')
def push_graph(elb_name, aws_access_key_id, aws_secret_access_key, aws_region_name, aws_profile_name,
               ssh_user, ssh_private_key, base_source_path, base_destination_path):
    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region_name,
        profile_name=aws_profile_name
    )
    # init resources and clients
    ec2 = session.resource('ec2')
    elb_client = session.client('elb')

    response = elb_client.describe_load_balancers(LoadBalancerNames=[elb_name])
    instances = response['LoadBalancerDescriptions'][0]['Instances']
    count_instances = len(instances)
    if count_instances <= 1:
        print 'Process aborted. You have {count} EC2 instance and ' \
              'this command requires to have 2 as minimum.'.format(count=count_instances)
        return

    # identify routers to push
    routers = []
    for subdir in os.listdir(base_source_path):
        if os.path.isdir(os.path.join(base_source_path, subdir)):
            graph_source_path = os.path.join(base_source_path, subdir, 'Graph.obj')
            if os.path.exists(graph_source_path):
                routers.append(subdir)
    if not routers:
        print 'Process aborted. No routers found at {path}'.format(path=base_source_path)
        return

    for instance in instances:
        instance_info = ec2.Instance(instance['InstanceId'])
        # remove instance from ELB
        print 'Removing instance {ip} from ELB {elb}'.format(ip=instance_info.public_ip_address, elb=elb_name)
        elb_client.deregister_instances_from_load_balancer(
            Instances=[instance],
            LoadBalancerName=elb_name
        )

        push_to_instance(instance_info.public_ip_address, ssh_user, ssh_private_key,
                         base_source_path, base_destination_path, routers)
        # add instance to ELB
        print 'Adding instance {ip} to ELB {elb}'.format(ip=instance_info.public_ip_address, elb=elb_name)
        elb_client.register_instances_with_load_balancer(
            LoadBalancerName=elb_name,
            Instances=[instance]
        )

if __name__ == '__main__':
    push_graph()