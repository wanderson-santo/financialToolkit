# Versionamento e release

## Estado atual

- Repositório: `https://github.com/wanderson-santo/financialToolkit`
- Branch principal: `main`
- Versão do aplicativo: definida em `app/__init__.py` (`__version__`)
- Baseline inicial: `v0.1.0`
- Versionamento semântico (`MAJOR.MINOR.PATCH`); durante a fase 0.x, mudanças
  incompatíveis podem ocorrer em versões `MINOR`.

## Branches

- `main` deve permanecer estável e com os testes passando.
- Mudanças pequenas podem ser commitadas diretamente em `main`.
- Mudanças maiores ou arriscadas usam branches curtas:
  - `feat/<descricao>` — nova funcionalidade
  - `fix/<descricao>` — correção
  - `docs/<descricao>` — documentação
  - `chore/<descricao>` — manutenção
- Ao concluir, faça merge em `main` e apague a branch.

## Commits

Um commit por tarefa do backlog, com o ID (`FT-xxx`) no assunto ou no corpo.

Formato recomendado:

```text
tipo: resumo curto no imperativo (FT-xxx)

Por que a mudança foi feita e o que muda para o usuário.
```

Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.

### Checklist antes de commitar

- [ ] `python -m unittest discover -s tests -t .` passa
- [ ] `python -m compileall -q app core modules tests` passa
- [ ] `git diff --check` sem problemas de espaço
- [ ] `git status --short` mostra apenas arquivos intencionais
- [ ] `docs/TODO.md` atualizado (tarefa marcada e status)
- [ ] nenhum segredo, banco local, planilha real ou dado financeiro no diff
- [ ] nenhum arquivo de `.venv/`, `build/`, `dist/` ou `__pycache__/`

Verificação rápida de artefatos versionados:

```bash
git ls-files | grep -E '(^|/)(\.venv|build|dist|__pycache__)/|\.pyc$|\.log$'
```

A saída deve ser vazia.

## Release

- [ ] Escopo da versão concluído no `docs/TODO.md`
- [ ] suíte completa verde em um clone limpo
- [ ] `__version__` em `app/__init__.py` atualizado
- [ ] README e limitações revisados
- [ ] documentação de arquitetura/auditoria atualizada quando aplicável
- [ ] `git status` limpo e `main` sincronizada com `origin/main`
- [ ] tag anotada criada:

```bash
git tag -a vX.Y.Z -m "Finance Toolkit vX.Y.Z"
git push origin main
git push origin vX.Y.Z
```

- [ ] confirmar a tag no GitHub e, se desejado, publicar um Release com o resumo

## Validação em clone limpo

```bash
git clone git@github.com:wanderson-santo/financialToolkit.git /tmp/finance_toolkit_clone
cd /tmp/finance_toolkit_clone
python -m unittest discover -s tests -t .
```

O clone não deve conter artefatos de build, ambiente virtual nem arquivos locais.
