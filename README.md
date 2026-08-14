# baixador-youtube

Automação em Python para download sequencial e em lote de mídias MP3 e MP4 com suporte a filas e autenticação.

---

## O problema

1. **O que é:** O **baixador-youtube** é um utilitário em Python com interface gráfica/batch para download de áudios e vídeos.
2. **Qual necessidade ataca:** Facilita o download de listas de vídeos e áudios em alta qualidade sem propagandas ou limites.
3. **Por que existe:** Ferramentas online possuem limites de download, convertem áudio em baixa qualidade ou exigem captchas.
4. **Qual o objetivo:** Permitir baixar playlists inteiras e filas de links com conversão MP3/MP4 direta.

---

## Recursos

- **Fila de downloads** — vai empilhando links e ele baixa **um por vez**, na ordem
- **MP3 e MP4** na mesma fila, sem se confundir
- **Playlists, álbuns, mixes e canais** — detecta sozinho pelo link
- **Não baixa a mesma música duas vezes** — histórico em SQLite que reconhece a
  faixa mesmo vindo de outro link
- **Proteção contra bloqueio** — pausas aleatórias entre as faixas
- **Login persistente** — usa sua conta para acessar conteúdo restrito
- **Retoma downloads interrompidos** e sobrevive a fechar o programa no meio
- Capa e metadados (título/artista) embutidos no MP3
- **Vídeos anônimos** — MP4 sai com nome UUID e sem metadado nenhum

---

## Instalação

### Pré-requisitos
- Python 3.10 ou superior
- FFmpeg instalado no sistema

### Instalação
```bash
git clone https://github.com/caducosilva/baixador-youtube.git
cd baixador-youtube
pip install -r requirements.txt
```

---

## Como usar

Interface gráfica (PySide6):
```bash
python app.py
```

Linha de comando:
```bash
python baixar.py                          # fila interativa no terminal
python baixar.py <url> [<url>...]         # baixa como MP3 (padrão)
python baixar.py --mp4 <url> [<url>...]   # baixa como MP4
```

---

## Configuração

Copie o arquivo `config.exemplo.json` para `config.json` e ajuste se necessário.

| Campo | Descrição | Padrão |
|---|---|---|
| `pasta_destino` | Diretório onde os downloads serão salvos | `./downloads` |
| `qualidade_audio` | Qualidade do bitrate MP3 | `320k` |

---

## Detalhes técnicos relevantes

Cada música baixada é registrada num banco SQLite (`historico.db`) com o **título
normalizado**, não só o ID do vídeo. Assim a mesma faixa é reconhecida mesmo vindo
de um link diferente:

```
AURORA - Runaway (Official Video)         →  "aurora runaway"
AURORA - Runaway [HD]                     →  "aurora runaway"
Aurora  Runaway (Official Music Video) 4K →  "aurora runaway"
```

As três são a mesma coisa — só a primeira baixa.

Rodar a mesma playlist de novo pega **só o que é novo**, o que é útil para acompanhar
um canal ou uma lista que cresce.

---

## Por que demora

O YouTube limita a velocidade por conexão. Medição real:

| | |
|---|---|
| Internet disponível | 13,7 MB/s |
| Entregue pelo YouTube | 0,44 MB/s |

Por música (faixa de ~3,7 min):

| Etapa | Tempo |
|---|---|
| download | 7,7s |
| conversão para MP3 | 4,6s |
| pausa anti-bloqueio | 3–8s |
| **total** | **~18s** |

Ou seja: **100 músicas ≈ 30 min**, **450 músicas ≈ 2h**.

A pausa é ~30% do tempo e existe de propósito: baixar centenas de faixas em rajada
é o caminho mais rápido para tomar bloqueio. Dá para reduzir em
`pausa_entre_musicas_min` / `_max`, por sua conta e risco.

---

## Login

O YouTube exige sessão autenticada até para conteúdo público — sem cookies aparece
`Sign in to confirm you're not a bot`.

Rode `python capturar_login.py`: abre uma janela do Chrome com **perfil separado** do seu
navegador do dia a dia, você faz login normalmente e os cookies são guardados em
`cookies/`. O yt-dlp renova a sessão sozinho a cada download.

> **Por que perfil separado?** O Chrome bloqueia leitura de cookies do perfil padrão
> (*App-Bound Encryption*) — nem fechando o navegador funciona. O perfil dedicado
> contorna isso sem tocar na sua navegação normal.

⚠️ A pasta `cookies/` equivale às suas contas **sem senha**. Está no `.gitignore`;
não compartilhe nem sincronize com nuvem.

---

## Onde os arquivos são salvos

```
MP3 → ~/Music                    com título, artista e capa
MP4 → ~/Videos/VideoDownloader   nome UUID, sem metadado nenhum
```

O `~` é expandido para a pasta do seu usuário em tempo de execução, então o
mesmo `config.json` funciona em qualquer máquina.

### Vídeos anônimos

Por padrão, todo MP4 baixado passa por uma limpeza:

| | Padrão do yt-dlp | Aqui |
|---|---|---|
| Nome do arquivo | `AURORA - I Went Too Far.mp4` | `98ad2cf0-e90b-4454-aaa7-1aa65b35e70e.mp4` |
| `title` / `artist` | preenchidos | removidos |
| `comment` | link do vídeo original | removido |
| `description` / `synopsis` | texto do vídeo | removidos |
| `date` / `genre` | preenchidos | removidos |

A limpeza usa `ffmpeg -c copy` — é remuxagem, **não recodifica**: leva menos de
um segundo e não perde qualidade.

Desligue com `"nome_aleatorio_mp4": false` e `"remover_metadados_mp4": false`.

> O histórico anti-duplicata continua funcionando: o título é gravado no banco
> antes da limpeza, então a música repetida ainda é reconhecida mesmo o arquivo
> não tendo mais nome identificável.
>
> Se quiser anonimato completo, use também `"pasta_por_playlist": false` —
> senão o nome da pasta ainda revela o conteúdo.

---

## Configuração (`config.json`)

| Campo | O que faz |
|---|---|
| `pasta_mp3` / `pasta_mp4` | onde salvar (aceita `~`) |
| `nome_aleatorio_mp4` | renomeia o vídeo para UUID |
| `remover_metadados_mp4` | apaga todas as tags do MP4 |
| `qualidade_mp3` | `0` = melhor (~245kbps), `2` = ~190kbps |
| `altura_maxima_mp4` | `1080`, `720`, `2160`… |
| `incluir_playlist` | `"auto"`, `true` ou `false` |
| `limite_itens_playlist` | `0` = tudo |
| `avisar_acima_de` | pergunta acima de N itens (`0` desliga) |
| `pausa_entre_musicas_min` / `_max` | pausa aleatória entre faixas |
| `evitar_duplicadas` | liga/desliga o histórico SQLite |
| `pasta_por_playlist` | subpasta com o nome da playlist |
| `numerar_playlist` | prefixo `01 - ` |
| `baixar_legendas` | baixa legendas no idioma de `idioma_legendas` |

---

## Estrutura

```
app.py                 janela principal (PySide6)
interface.py           atalho que abre o app.py
baixar.py              linha de comando unificada (MP3/MP4/fila)
baixar_mp3.py          entrada MP3
baixar_mp4.py          entrada MP4
capturar_login.py      cookies via CDP
ytdl/
├── baixar.py          motor de download
├── comum.py           configuração e login
├── fila.py            fila sequencial
├── interativo.py      modo interativo no terminal
└── historico.py       banco SQLite
```

---

## Testes

Para testar a captura de login:
```bash
python capturar_login.py
```

---

## Problemas comuns

| Mensagem de erro | Causa provável | Solução |
|---|---|---|
| `FFmpeg not found` | FFmpeg não instalado no PATH do sistema | Instale o FFmpeg e adicione a pasta `bin` às Variáveis de Ambiente |

---

## Apoie o projeto

Se este projeto te ajudou, considere fazer uma doação via PIX:

```
f74458dc-2a36-49bd-9250-1cef4365ebb8
```

---

## Licença

[MIT](LICENSE) — Carlos Eduardo
