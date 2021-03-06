import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as awsx from "@pulumi/awsx";
import * as eks from "@pulumi/eks";

const stack = pulumi.getStack()

const clusterTag = `kubernetes.io/cluster/lbrlabs-eks-${stack}`

// this defines a valid VPC that can be used for EKS
const vpc = new awsx.ec2.Vpc(`vpc-${stack}`, {
    cidrBlock: "172.16.0.0/24",
    subnets: [
        {
            type: "private",
            tags: {
                [clusterTag]: "owned",
                "kubernetes.io/role/internal-elb": "1",
            }
        },
        {
            type: "public",
            tags: {
                [clusterTag]: "owned",
                "kubernetes.io/role/elb": "1",
            }
        }],
    tags: {
        Name: `${stack}-vpc`,
    }
});

const kubeconfigOpts: eks.KubeconfigOptions = {profileName: "personal"};

const cluster = new eks.Cluster(`vpc-${stack}`, {
    providerCredentialOpts: kubeconfigOpts,
    name: `lbrlabs-eks-${stack}`,
    vpcId: vpc.id,
    privateSubnetIds: vpc.privateSubnetIds,
    publicSubnetIds: vpc.publicSubnetIds,
    instanceType: "t2.medium",
    desiredCapacity: 2,
    minSize: 1,
    maxSize: 2,
    createOidcProvider: true,
});

export const vpcId = vpc.id
export const clusterName = cluster.eksCluster.name
export const kubeconfig = cluster.kubeconfig
export const clusterOidcProvider = cluster.core.oidcProvider?.url
export const clusterOidcProviderArn = cluster.core.oidcProvider?.arn
