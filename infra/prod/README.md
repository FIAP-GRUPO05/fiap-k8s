# Referencia anterior de AWS Academy

Esta raiz usa `LabRole` e os parametros do laboratorio anterior. Ela nao e
aplicada na conta TWM e nao gerencia o cluster atual. A raiz ativa e
[`../platform`](../platform/README.md), que provisiona rede privada, EKS,
executores de deploy e a instalacao New Relic.

Nao execute `terraform apply` nesta pasta para provisionar a conta centralizada.
Os dashboards New Relic permanecem aqui como referencia para a migracao dos
recursos de monitoramento.
