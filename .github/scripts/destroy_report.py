"""Produce a redacted Markdown/HTML report even when teardown failed early."""
import argparse
from decimal import Decimal
import html
import json
import os
from pathlib import Path
import re


def as_html(markdown):
    def inline(text):
        text = html.escape(text)
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        return re.sub(r"\[([^\]]+)\]\((https://[^)]+)\)", r'<a href="\2">\1</a>', text)
    output, table = [], False
    for line in markdown.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                continue
            if not table:
                output.append("<table>")
                table = True
            css = "ok" if "✅" in line else "bad" if "❌" in line else ""
            output.append('<tr class="' + css + '">' + "".join("<td>" + inline(cell) + "</td>" for cell in cells) + "</tr>")
            continue
        if table:
            output.append("</table>")
            table = False
        if line.startswith("## "):
            output.append("<h2>" + inline(line[3:]) + "</h2>")
        elif line.startswith("# "):
            output.append("<h1>" + inline(line[2:]) + "</h1>")
        elif line:
            output.append("<p>" + inline(line) + "</p>")
    if table:
        output.append("</table>")
    return "\n".join(output)


def render(directory):
    execution = directory / "execution.json"
    data = json.loads(execution.read_text()) if execution.exists() else {
        "status": "blocked", "errors": ["A execução não produziu auditoria final; não é possível confirmar desligamento."],
        "before": {}, "after": {"errors": ["Sem inventário final"]}, "costs": {"available": False}}
    after = data.get("after", {})
    remaining = {(item["kind"], item["id"]) for item in after.get("resources", [])}
    free = {(item["kind"], item["id"]): item for item in after.get("free_resources", [])}
    complete = bool(data.get("after")) and not after.get("errors")
    lines = ["# Desmontagem AWS — relatório de execução", "",
             f"**Conta:** 456687462806 · **Região:** sa-east-1 · **Execução:** {data.get('status', 'unknown')}", "",
             "## Recursos verificados", "", "| Verificação | Recurso | Resultado |", "|---|---|---|"]
    for item in data.get("before", {}).get("resources", []):
        key = item["kind"], item["id"]
        if not complete:
            icon, status = "⚠️", "Auditoria incompleta; remoção não comprovada"
        elif key in remaining:
            icon, status = "❌", "Ainda encontrado; requer acompanhamento"
        elif key in free:
            icon, status = "✅", "Fora de operação; exclusão agendada, sem tarifa de retenção/chave enquanto nesse estado"
        else:
            icon, status = "✅", "Não encontrado na auditoria final"
        lines.append(f"| {icon} | `{item['kind']}: {item['id']}` | {status} |")
    if not data.get("before", {}).get("resources"):
        lines.append("| ⚠️ | Inventário inicial ausente ou vazio | Nenhuma remoção será presumida |")
    if complete:
        for item in after.get("confirmed_absences", []):
            if not any(before["kind"] == item["kind"] for before in data.get("before", {}).get("resources", [])):
                lines.append(f"| ✅ | {item['label']} | Ausência confirmada; não foi excluído por esta execução |")
    for key in sorted(remaining):
        if key not in {(i["kind"], i["id"]) for i in data.get("before", {}).get("resources", [])}:
            lines.append(f"| ❌ | `{key[0]}: {key[1]}` | Recurso residual encontrado |")
    lines += ["", "## O que permanece", "", "| Estado | Recurso | Cobrança direta de retenção/provisionamento |", "|---|---|---|"]
    for item in after.get("free_resources", []):
        lines.append(f"| ℹ️ {item['state']} | `{item['kind']}: {item['id']}` | {item['reason']} |")
    costs = data.get("costs", {})
    lines += ["", "## Custos históricos", "",
              f"Período: {costs.get('start', 'não disponível')} a {costs.get('end_exclusive', 'não disponível')} (fim exclusivo).",
              costs.get("attribution", "Sem atribuição comprovada de custos."), ""]
    if costs.get("available"):
        lines += ["| Serviço | Consumo/taxas (USD) | Créditos/reembolsos (USD) | Saldo (USD) |", "|---|---:|---:|---:|"]
        for service in costs.get("services", []):
            consumption = Decimal(str(service.get("consumption", 0)))
            credits = Decimal(str(service.get("credits", 0))) + Decimal(str(service.get("refunds", 0)))
            amount = Decimal(str(service["amount"]))
            lines.append(f"| {service['service']} | {consumption:.6f} | {credits:.6f} | {amount:.6f} |")
        lines += [f"| **Total da conta no período** | **{Decimal(str(costs.get('consumption', 0))):.6f}** | **{Decimal(str(costs.get('credits', 0))) + Decimal(str(costs.get('refunds', 0))):.6f}** | **{Decimal(str(costs.get('total', 0))):.6f}** |", "",
                  "Consumo/taxas são os lançamentos sem Credit/Refund; saldo inclui esses créditos e reembolsos. Saldo próximo de zero não significa que os recursos não consumiram serviços.",
                  "⚠️ Valores estimados pela AWS." if costs.get("estimated") else "Valores retornados pela AWS sem marcação Estimated."]
    else:
        lines += ["⚠️ **Custo indisponível. Não equivale a US$ 0,00.**", costs.get("error", "Dados não coletados.")]
    lines += ["", "O custo por serviço da conta não será distribuído artificialmente entre recursos. Custo exato por recurso requer dados de faturamento com esse detalhamento e período compatível. Dados de faturamento podem chegar depois da exclusão.", "",
              "## Sincronização das branches", "", "| Repositório | Branch | Commit confirmado |", "|---|---|---|"]
    for item in data.get("sync", []):
        lines.append(f"| {item['repository']} | {item['branch']} | `{item['sha']}` |")
    errors = data.get("errors", []) + after.get("errors", [])
    lines += ["", "## Pendências", ""]
    lines += ["- ❌ " + error for error in errors] if errors else ["Nenhum erro operacional registrado; observar as limitações de cobertura e faturamento abaixo."]
    lines += ["", "## Limites da comprovação", "",
              "- A auditoria detalha os serviços enumerados em sa-east-1 e pesquisa a tag Project nas regiões habilitadas. Recursos etiquetados fora do escopo ou não suportados bloqueiam a confirmação. Recursos sem tag em serviços não enumerados e compromissos de faturamento exigem conferência própria.",
              "- Recursos ausentes e acesso negado são estados diferentes. Falha de consulta impede confirmação de desligamento.",
              "- IAM/OIDC não têm tarifa direta de provisionamento, mas permissões remanescentes podem permitir novo uso se a manutenção for desativada.",
              "- Segredos e KMS podem permanecer agendados para exclusão, fora de operação. Cancelar a exclusão pode restabelecer cobrança.",
              "- New Relic, GitHub, plano de suporte e compromissos de cobrança exigem conferência separada.",
              "- **Não há declaração automática de custo zero futuro.** A ausência dos recursos auditados e os custos históricos são evidências distintas.", "",
              "Fontes das regras de retenção: [Secrets Manager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/manage_delete-secret.html), [KMS](https://aws.amazon.com/kms/pricing/).", ""]
    markdown = "\n".join(lines)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.md").write_text(markdown, encoding="utf-8")
    # The downloadable HTML is self contained and never runs scripts.
    document = "<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>Desmontagem AWS</title><style>body{margin:40px auto;max-width:1200px;padding:0 24px;background:#f3f6fa;color:#18283c;font:16px/1.6 system-ui}h1,h2{color:#164e80}table{width:100%;border-collapse:collapse;background:white;margin:20px 0}td{border:1px solid #dce4ef;padding:10px;overflow-wrap:anywhere}tr:first-child{background:#164e80;color:white;font-weight:bold}.ok{background:#e8f7ef}.bad{background:#fff0ee}code{overflow-wrap:anywhere}a{color:#1761a0}</style>" + as_html(markdown) + "</html>"
    (directory / "index.html").write_text(document, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as output:
            output.write(markdown)
    print("Report generated: " + str(directory / "index.html"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=Path("destroy-report"))
    render(parser.parse_args().directory)
