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

## Membros da equipe

<table>
  <tr>
    <td align="center" width="160">
      <a href="https://www.linkedin.com/in/wesslima/" title="Wesley Lima">
        <img src="https://raw.githubusercontent.com/FIAP-GRUPO05/fiap-docs/main/assets/team/wesley-lima.jpg" width="100" height="100" alt="Foto de Wesley Lima"><br>
        <sub><b>Wesley Lima</b></sub>
      </a><br><sub>Backend Engineer</sub>
    </td>
    <td align="center" width="160">
      <a href="https://www.linkedin.com/in/tim-morgenstern-4581911b1/" title="Tim Morgenstern">
        <img src="https://raw.githubusercontent.com/FIAP-GRUPO05/fiap-docs/main/assets/team/tim-morgenstern.jpg" width="100" height="100" alt="Foto de Tim Morgenstern"><br>
        <sub><b>Tim Morgenstern</b></sub>
      </a><br><sub>Backend Engineer</sub>
    </td>
    <td align="center" width="160">
      <a href="https://www.linkedin.com/in/matheus-pitas-baptista/" title="Matheus Pitas Baptista">
        <img src="https://raw.githubusercontent.com/FIAP-GRUPO05/fiap-docs/main/assets/team/matheus-pitas.jpg" width="100" height="100" alt="Foto de Matheus Pitas Baptista"><br>
        <sub><b>Matheus Pitas Baptista</b></sub>
      </a><br><sub>Backend Engineer</sub>
    </td>
  </tr>
</table>
