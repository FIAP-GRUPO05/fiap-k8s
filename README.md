# fiap-k8s

Infraestrutura da plataforma Kubernetes do projeto: EKS, rede, deploy privado, permissões AWS e observabilidade New Relic, definidos como código.

📚 **[Documentação principal — fiap-docs](https://github.com/FIAP-GRUPO05/fiap-docs)** · [Guia da plataforma](https://github.com/FIAP-GRUPO05/fiap-docs/blob/main/guides/platform.md)

## Requisitos

- Terraform 1.13 ou superior e Python 3.12.
- AWS CLI, kubectl e Helm apenas para as operações administrativas descritas na documentação central.

## Validar localmente

Na raiz deste repositório:

```powershell
terraform -chdir=infra/platform init -backend=false
terraform -chdir=infra/platform validate
python -m unittest discover -s .github/scripts -p 'test_*.py' -v
```

A validação acima não cria um cluster. Topologia, bootstrap e observabilidade estão no [guia central](https://github.com/FIAP-GRUPO05/fiap-docs/blob/main/guides/platform.md).
Consulte [CI/CD](https://github.com/FIAP-GRUPO05/fiap-docs/blob/main/operations/cicd.md), [operação de desmontagem](https://github.com/FIAP-GRUPO05/fiap-docs/blob/main/operations/destroy-aws.md) e o [estado da infraestrutura](https://github.com/FIAP-GRUPO05/fiap-docs/blob/main/operations/infrastructure-state.md).
