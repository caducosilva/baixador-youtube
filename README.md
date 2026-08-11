# Baixador YouTube / YouTube Music

Baixe músicas em **MP3** e vídeos em **MP4** do YouTube e do YouTube Music, com fila,
controle de duplicatas e proteção contra bloqueio.

Feito para uso pessoal no Windows, com interface simples e tudo rodando **localmente** —
nenhum dado sai do seu computador.

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

---

## Instalação

Precisa de **Python 3.10+**, **ffmpeg** e **yt-dlp**.

```bash
pip install -U yt-dlp
winget install Gyan.FFmpeg
```

Depois é só baixar este repositório e copiar `config.exemplo.json` para `config.json`,
ajustando as pastas de saída.

---

## Como usar

| Quero | Abro |
|---|---|
| **Fila com interface** (recomendado) | `FILA.bat` |
| Baixar MP3 pela linha de comando | `MP3.bat` |
| Baixar MP4 pela linha de comando | `MP4.bat` |
| Configurar meu login | `CAPTURAR-LOGIN.bat` |

### A fila

Cole o link, escolha MP3 ou MP4, clique em **+ Adicionar**. Pode empilhar quantos
quiser — músicas soltas, vídeos e playlists misturados.

Baixa **um por vez**. Quando termina tudo daquele link, pega o próximo sozinho.

- Cole **vários links de uma vez** (separados por espaço)
- **Pausar** espera o item atual terminar, não corta no meio
- **▲** sobe na fila · **✕** remove
- A fila fica salva — fechar o programa não perde a lista
- Mostra o progresso da playlist (`faixa 12/447`)

### Linha de comando

```bash
MP3.bat https://youtu.be/xxxx
MP3.bat --playlist https://www.youtube.com/playlist?list=PLxxxx
MP4.bat --so-um "https://music.youtube.com/watch?v=xxx&list=RDxxx"
```

| Opção | Efeito |
|---|---|
| *(nenhuma)* | detecta sozinho pelo link |
| `--playlist` ou `-p` | força a playlist inteira |
| `--so-um` ou `-1` | força só aquele item |

---

## Playlists

Detecta automaticamente:

| Link | Resultado |
|---|---|
| `youtube.com/watch?v=abc` | só esse item |
| `youtube.com/playlist?list=PLxxx` | playlist inteira |
| `music.youtube.com/playlist?list=OLAK...` | álbum inteiro |
| `youtube.com/@canal/videos` | canal inteiro |
| `watch?v=abc&list=RDxxx` | mix inteiro |

Playlists viram pastas organizadas:

```
Music/yt-dlp/
└── Replay Mix/
    ├── 01 - AURORA - I Went Too Far.mp3
    ├── 02 - Trance.mp3
    └── 03 - Temperance.mp3
```

Acima de 20 itens ele pergunta antes de começar, mostrando quantos são.

---

## Sem músicas repetidas

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

Rode `CAPTURAR-LOGIN.bat`: abre uma janela do Chrome com **perfil separado** do seu
navegador do dia a dia, você faz login normalmente e os cookies são guardados em
`cookies/`. O yt-dlp renova a sessão sozinho a cada download.

> **Por que perfil separado?** O Chrome bloqueia leitura de cookies do perfil padrão
> (*App-Bound Encryption*) — nem fechando o navegador funciona. O perfil dedicado
> contorna isso sem tocar na sua navegação normal.

⚠️ A pasta `cookies/` equivale às suas contas **sem senha**. Está no `.gitignore`;
não compartilhe nem sincronize com nuvem.

---

## Configuração (`config.json`)

| Campo | O que faz |
|---|---|
| `pasta_mp3` / `pasta_mp4` | onde salvar |
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
FILA.bat               interface da fila
MP3.bat / MP4.bat      linha de comando
CAPTURAR-LOGIN.bat     captura do login
interface.py           janela (Tkinter)
baixar_mp3.py          entrada MP3
baixar_mp4.py          entrada MP4
capturar_login.py      cookies via CDP
ytdl/
├── baixar.py          motor de download
├── comum.py           configuração e login
├── fila.py            fila sequencial
└── historico.py       banco SQLite
testes/
└── teste_completo.py  bateria de testes
```

---

## Testes

```bash
python testes/teste_completo.py
```

Cobre: mesma música pedida várias vezes, músicas diferentes, playlists,
e fila com MP3 e MP4 misturados.

---

## Problemas comuns

| Mensagem | O que fazer |
|---|---|
| `Sign in to confirm you're not a bot` | rode `CAPTURAR-LOGIN.bat` |
| `Failed to decrypt with DPAPI` | use `CAPTURAR-LOGIN.bat` (perfil separado) |
| `Video unavailable` | removido ou bloqueado na região |
| `429 / Too Many Requests` | espere alguns minutos; aumente as pausas |
| Extração quebrada | `pip install -U yt-dlp` |

O yt-dlp precisa ser atualizado com frequência — os sites mudam e quebram a extração.

---

## Apoie o projeto

Se este projeto te ajudou, considere fazer uma doação via PIX:

```
f74458dc-2a36-49bd-9250-1cef4365ebb8
```

---

## Aviso

Ferramenta para **uso pessoal**: baixar conteúdo que você tem direito de acessar,
como suas próprias playlists e material de domínio público ou livre.

Respeite os direitos autorais e os termos de uso das plataformas. O uso é de
responsabilidade de quem executa.

---

## Licença

[MIT](LICENSE) — Carlos Eduardo
