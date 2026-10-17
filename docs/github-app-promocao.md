# GitHub App para promocao automatica

Os quatro repositorios usam o mesmo workflow para criar os PRs de promocao. O
`GITHUB_TOKEN` consegue abrir esses PRs, mas o GitHub pode deixar as esteiras
iniciadas por eles aguardando aprovacao. Um GitHub App da organizacao permite
que as validacoes comecem automaticamente.

1. Em **FIAP-GRUPO05 > Settings > Developer settings > GitHub Apps**, crie um
   aplicativo privado, por exemplo `fiap-promocao-ci`.
2. Conceda apenas as permissoes de repositorio **Contents: Read and write** e
   **Pull requests: Read and write**. `Metadata: Read-only` e implicita. O
   workflow nao depende de webhooks; desative-os se o formulario permitir.
3. Instale o aplicativo na organizacao selecionando somente
   `fiap-application`, `fiap-lambda`, `fiap-k8s` e `fiap-database`.
4. Para voltar as configuracoes do App, abra **FIAP-GRUPO05 > Settings >
   Developer settings > GitHub Apps** e clique em **Edit** ao lado do App.
   Na pagina de configuracao, localize **Client ID** e copie esse valor. Ele
   nao e o **App ID** e nao e o **Client secret**; estes dois nao sao usados
   pelo workflow.
5. No menu lateral dessa mesma pagina, abra **Credentials > Key pairs > New
   key**. O GitHub baixara um arquivo `.pem`. Em algumas versoes da interface,
   a secao aparece como **Private keys > Generate a private key**. Guarde o
   arquivo fora dos repositorios e nao envie seu conteudo por chat.
6. Em **FIAP-GRUPO05 > Settings > Secrets and variables > Actions > Variables >
   New organization variable**, use o nome `FIAP_PROMOTION_APP_CLIENT_ID` e
   cole no campo **Value** o Client ID copiado no passo 4. Selecione acesso
   apenas aos quatro repositorios.
7. Na aba **Secrets > New organization secret**, use o nome
   `FIAP_PROMOTION_APP_PRIVATE_KEY` e cole no campo **Secret** o conteudo
   completo do `.pem`, inclusive as linhas `BEGIN` e `END`. Selecione os
   mesmos quatro repositorios. Nao use o Client secret nesse campo.
8. Envie um commit em `feature/*`. No job `Propose`, a etapa `10a` deve gerar o
   token. O PR gerado pelo aplicativo deve iniciar o job `Verify` sem uma
   aprovacao adicional. Repita a verificacao ao promover para `release/vX.Y.Z`
   e `prod`.

Enquanto a variavel nao existir, o workflow continua com `GITHUB_TOKEN` e
exibe um aviso. Nessa condicao, o GitHub pode exigir aprovacao manual da
execucao criada pelo PR automatico.
