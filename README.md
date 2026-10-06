# CurseForge ModPackを検証し、手動で提出する

Minecraft 1.21.1・NeoForge 21.1.250のクライアント構成（MOD 20個）と、CurseForgeアプリの正式exportを検証・手動提出する処理を管理します。Python 3.12以降の標準ライブラリを使います。公開済みのMODはファイルIDで参照し、jarや個人の接続情報は収録しません。投稿トークン・有効な提出設定・正式exportは未設定です。

## クライアント構成を再現する

[構成と導入案内](profiles/create-client-local/README.md)に、固定した20個のファイルIDと確認状況をまとめています。名称は仮です。ゲーム起動・サーバー独自設定は未確認です。

```bash
python3 -m unittest discover -s tests -v
python3 scripts/local_pack.py --output /tmp/create-client-local-draft.zip
```

生成済みの[取込用ZIP](https://github.com/aiagate/minecraft-modpack-release/raw/refs/heads/feature/create-client-reconstruction-20261006/downloads/create-client-local-draft.zip)も取得できます。WindowsのCurseForgeで **Minecraft → Import → Import Profile .zip → Choose .zip file** を選ぶと、新しいプロフィールへ取り込みます。GitHubの **Code → Download ZIP** はリポジトリ全体のアーカイブで、取込用ZIPとは異なります。Appへの実際の取込・起動はまだ確認していません。

`local_pack.py` はmanifestと一覧の整合性を検証し、ローカル取込用の草案を再現します。jarのダウンロード・実行・公開提出は行いません。この草案を `packs/` に置かず、公開提出には以下の正式export手順を使ってください。

## 初回設定はアプリのexportから始める

1. CurseForge上の初回プロジェクトは自分で作成し、project IDを控えます。
2. アプリで配布専用のプロファイルを用意し、必要なファイルだけを選んでexportします。生成されたmanifestは手編集しません。提出用の `release.py` もmanifestの作成・修正・ZIPの再梱包は行いません。
3. ZIPをGitに追加する**前に**、全収録ファイルを確認します。ワールド、options.txt、ログ、認証情報、個人用サーバー情報を取り除く必要があれば、元プロファイルを修正してアプリから再exportします。設定ファイル内のドメイン名や任意の秘密値は完全には自動判定できないため、人による内容確認が必須です。
4. 確認したZIPを `packs/pack.zip` に置きます。`packs/` には現行ZIPを1つだけ置き、旧版はGit履歴に残します。
5. `cp release.example.json release.json` で設定を作り、project ID、export内のMinecraft版とloader ID、表示名を入力します。`game_version_names` はMinecraft版、対応Loader名、`Client` の3つです。公式Game Versions API `/api/game/versions` で正式名を確認してください。実在する版番号はこの例に埋めていません。
6. `sha256sum packs/pack.zip` の値を `reviewed_sha256` に記入します。この値は内容レビュー済みのZIPを特定するためのものです。レビューせずに値だけ更新しないでください。
7. `CHANGELOG.md` を今回の変更内容に置き換えます。その全文が提出用変更履歴になります。

```bash
python3 -m unittest discover -s tests -v
python3 scripts/release.py --zip packs/pack.zip
```

既定は通信しないdry-runです。project ID、設定、変更履歴、ZIPが未設定なら停止します。成功後にZIP・`release.json`・変更履歴をコミットしてください。`.gitignore` はZIPの内部を検査しません。秘密を一度コミットするとGit履歴に残るため、事前検査が必要です。

## 投稿はmainから手動実行する

このリポジトリは公開です。個人向け資料やサーバー情報は置かず、正式exportを追加する際も全内容を公開可能か確認します。GitHub Actionsの `Manual CurseForge submission` をmainから実行し、まず `submit=false` で確認します。PRとpushの検証workflowは投稿secretを参照しません。

実提出を始めるときだけ、自分で発行した投稿用トークンをGitHub Actions Secret `CURSEFORGE_API_TOKEN` に登録し、`submit=true` を選びます。コード・設定・ZIPをレビューした信頼できるmainだけを使ってください。write権限を持つ人はworkflowを書き換えられるため、共同編集者を限定し、運用に応じてmainの保護や環境承認を追加してください。ひな形の作成ではSecrets登録や保護設定の変更は行いません。

投稿ステップ内でZIPをメモリに一度読み込み、検証した同じバイト列を1回だけ送信します。送信先は固定のHTTPSホスト、トークンは `X-Api-Token` ヘッダーだけに設定します。リダイレクト追従・自動再送・応答本文のログ出力はありません。GitHub Actionsの再実行も再投稿になるため、失敗やタイムアウト時は作者画面で受付状況を確認してから判断してください。同時投稿は直列化しますが、重複投稿を永続的に防ぐ仕組みではありません。

APIのfile ID取得は受付成功を意味し、審査完了ではありません。`isMarkedForManualRelease=true` で提出するため、承認後の公開操作も作者画面で行います。サーバーパック提出・Minecraftサーバーへの配置は扱いません。

## 自動検査には保守的な制限がある

検査対象はZIP構造、zip-slip、重複パス、symlink等の特殊ファイル、暗号化、CRC、サイズ、manifestの基本構造、Minecraft版・Loaderと提出メタデータの一致です。ZIPは展開しません。

このリポジトリ独自の上限は圧縮90 MiB、展開256 MiB、1ファイル32 MiB、1万エントリ、圧縮率200倍です。CurseForge公式の上限を示すものではありません。GitHubへの通常Git保存を想定しています。

初期版ではoverrideはUTF-8テキストだけを許可し、JAR・入れ子アーカイブ・バイナリを拒否します。URL、IPアドレス、秘密値らしい記述も拒否するため、正当な公開URL等で停止する場合があります。必要なら対象ファイルと配布権を確認し、検証方針を明示的に変更してください。検査を通すためにmanifestを加工してはいけません。

自動検査はアプリ生成の真正性、任意の秘密値、全MODの掲載状態・互換性・配布許可、実ゲームでの起動を保証しません。MODの参照先・Loaderタグ・配布権は提出前に人が確認し、アプリへの再importと起動試験を行ってください。`tests/` のmanifestは検査用の合成fixtureで、配布用exportではありません。

## 参照した公式仕様

2026-10-04確認。

- [CurseForge Upload API](https://support.curseforge.com/support/solutions/articles/9000197321-curseforge-upload-api): multipartのmetadata/file、認証ヘッダー、版名指定、受付file ID、手動公開設定。
- [Moderation Policies](https://support.curseforge.com/support/solutions/articles/9000197279-project-and-modpack-moderation-policies): アプリ生成形式、manifest手編集禁止、Loaderの整合性、収録MODの配布条件。審査に合わせたプロジェクト説明や画像の用意も必要です。
- [GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use): 最小権限、Actionの完全SHA固定、信頼できるコードだけにSecretsを渡す運用。
