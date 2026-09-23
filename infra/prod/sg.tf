resource "aws_security_group" "sg" {
  name        = "${var.projectName}-sg"
  description = "Expor service do cluster"
  vpc_id      = aws_vpc.main.id

}

# --------------------------- INGRESS ---------------------------

resource "aws_vpc_security_group_ingress_rule" "allow_postgres" {
  security_group_id = aws_security_group.sg.id
  description       = "Postgres"
  from_port         = 5432
  to_port           = 5432
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "allow_internal" {
  security_group_id            = aws_security_group.sg.id
  description                  = "Permite trafego interno completo entre cluster e nos"
  ip_protocol                  = "-1"
  referenced_security_group_id = aws_security_group.sg.id
}

resource "aws_vpc_security_group_ingress_rule" "allow_nodeports" {
  security_group_id            = aws_security_group.sg.id
  description                  = "Permite trafego das NodePorts do EKS"
  from_port                    = 30000
  to_port                      = 32767
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg.id
}

resource "aws_vpc_security_group_ingress_rule" "allow_api" {
  security_group_id = aws_security_group.sg.id
  description       = "Permite acesso externo a API"
  from_port         = 8080
  to_port           = 8080
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "allow_metrics_server" {
  security_group_id            = aws_security_group.sg.id
  description                  = "Permite trafego interno do Metrics Server e Kubelet"
  from_port                    = 10250
  to_port                      = 10251
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg.id
}

# --------------------------- EGRESS ----------------------------

resource "aws_vpc_security_group_egress_rule" "allow_all" {
  security_group_id = aws_security_group.sg.id
  description       = "All"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}
