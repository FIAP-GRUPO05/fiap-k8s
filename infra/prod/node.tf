resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "Nodeg-${var.projectName}"
  node_role_arn   = data.aws_iam_role.lab_role.arn
  subnet_ids      = [aws_subnet.private.id, aws_subnet.public.id]
  instance_types  = ["t3.medium"]


  scaling_config {
    desired_size = 2
    max_size     = 3
    min_size     = 1
  }

  update_config {
    max_unavailable = 1
  }

 
  depends_on = [
    aws_eks_cluster.main,
    aws_eks_access_entry.access_entry_lab,
    aws_internet_gateway.main,
    aws_route_table_association.rt_association_public,
    aws_route_table_association.rt_association_private,
  ]
}