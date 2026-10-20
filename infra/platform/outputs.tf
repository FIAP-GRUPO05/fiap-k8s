output "cluster_name" {
  value = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.main.endpoint
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "vpc_cidr" {
  value = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "cluster_security_group_id" {
  value = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
}

output "lambda_security_group_id" {
  value = aws_security_group.lambda.id
}

output "secrets_manager_endpoint_security_group_id" {
  value = aws_security_group.secrets_manager_endpoint.id
}

output "codebuild_deploy_security_group_id" {
  value = aws_security_group.codebuild_deploy.id
}
