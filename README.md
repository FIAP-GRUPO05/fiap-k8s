# fiap-k8s

Infraestrutura da plataforma Kubernetes do projeto: EKS, rede, deploy privado, permissões AWS e observabilidade New Relic, definidos como código.

📚 **[Documentação principal — fiap-docs](https://github.com/FIAP-GRUPO05/fiap-docs)**

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

A validação não cria um cluster. Consulte a arquitetura e a documentação do projeto no [fiap-docs](https://github.com/FIAP-GRUPO05/fiap-docs).

## Membros da equipe

<table>
  <tr>
    <td align="center" width="160">
      <a href="https://www.linkedin.com/in/wesslima/" title="Wesley Lima">
        <img src="https://media.licdn.com/dms/image/v2/D4D03AQG__sMSpl_SEg/profile-displayphoto-scale_400_400/B4DaEHvVltHsAg-/0/1791131212617?e=1794441600&amp;v=beta&amp;t=VPPE-aIk2CNR6rhd3yPIdsPjOuVyl7gdsCxP6AlAlpg" width="100" height="100" alt="Foto de Wesley Lima"><br>
        <sub><b>Wesley Lima</b></sub>
      </a><br><sub>Backend Engineer</sub>
    </td>
    <td align="center" width="160">
      <a href="https://www.linkedin.com/in/tim-morgenstern-4581911b1/" title="Tim Morgenstern">
        <img src="https://media.licdn.com/dms/image/v2/C4E03AQG57Du9tsCS5A/profile-displayphoto-shrink_400_400/profile-displayphoto-shrink_400_400/0/1643980434981?e=1794441600&amp;v=beta&amp;t=6fVFPP0UXkaUU6K77-XJ3fPtGR2YvE1KRoRn9ze-Vog" width="100" height="100" alt="Foto de Tim Morgenstern"><br>
        <sub><b>Tim Morgenstern</b></sub>
      </a><br><sub>Backend Engineer</sub>
    </td>
    <td align="center" width="160">
      <a href="https://www.linkedin.com/in/matheus-pitas-baptista/" title="Matheus Pitas Baptista">
        <img src="https://media.licdn.com/dms/image/v2/D4D03AQHFS4VJk5WteA/profile-displayphoto-scale_400_400/B4DZv_LwbmHYAg-/0/1769512832179?e=1794441600&amp;v=beta&amp;t=gaI3wzS0F5BnXd5z0V9sS90uFcyxOLiK0vgWPnzMOJg" width="100" height="100" alt="Foto de Matheus Pitas Baptista"><br>
        <sub><b>Matheus Pitas Baptista</b></sub>
      </a><br><sub>Backend Engineer</sub>
    </td>
  </tr>
</table>
