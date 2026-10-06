# OKD Server Modpack

**OKD Server Modpack** はサーバー参加用クライアントの取込パックです。専用サーバーを実行するZIPではありません。Minecraft 1.21.1・NeoForge 21.1.250の20MOD構成を管理します。Gitには参照表・設定・スクリプト・テスト・変更履歴を置き、ZIPは置きません。正式提出はCurseForge Appのexportをレビューしてから、GitHub Actionsで検証・提出します。投稿Token、正式export、実際のproject IDは未設定です。

## GitとZIPの保管先

| 管理対象 | 保管先 |
| --- | --- |
| MOD参照manifest・mods.tsv・検証/提出スクリプト・workflow・release.json・CHANGELOG | Git |
| レビュー前の正式App export | 手元の非共有フォルダ。Git、Release、Actions artifactへ載せない |
| 全内容レビューとローカル検査を通した正式export | 同じリポジトリの公開Release asset |
| 同一run内で提出jobへ渡す検証済みexportとreceipt | Actions artifact、30日保持 |
| 自動生成した取込草案とチェックサム | Validate workflowのbuild artifact、14日保持 |

このリポジトリは公開です。公開Release assetは取得者を限定できず、CurseForge審査より先にGitHubで公開されます。未審査という理由で私的情報を含めてよいわけではありません。公開可否の確認が済むまで、手元の非共有フォルダにだけ保管してください。CurseForge承認までZIPを非公開にしたい運用には、この公開Release asset方式を使わず、別途非公開の保管設計が必要です。

同じリポジトリのasset IDを指定する方式は、外部ストレージ用の資格情報や任意URL設定が不要です。取得処理は公開GETだけで、固定リポジトリのasset APIと許可したGitHub配信ホストへしか接続しません。最新版やファイル名で自動選択せず、IDとレビュー済みSHA256で内容を固定します。Release assetの保管はGitの履歴サイズを増やしません。以前コミットしたZIPは、削除の変更を適用しても過去のGit履歴には残ります。履歴の書換えは行いません。

## 命名と旧プレビュー

表示名は `OKD Server Modpack`、プロフィールのパスと配布slugは `okd-server-modpack` に統一します。取込草案は `okd-server-modpack-import-preview.zip` とし、正式提出用の一時ZIPとmultipartのファイル名は `okd-server-modpack.zip` です。`Server` は参加先を示し、サーバー実行パックを意味しません。正式App exportの名前はApp上で設定し、生成manifestを手編集しません。

[旧取込プレビュー](https://github.com/aiagate/minecraft-modpack-release/releases/tag/preview-create-client-20261006-9f7671a)は履歴として残します。改名版は草案manifestの表示名だけを変え、20件のMOD参照・版・author・空のoverridesを維持します。ZIPのバイトとSHA256は変わるため、改名版のチェックサムで検証してください。旧リンク・タグ・assetは削除や上書きをしません。

## 取込草案を生成する

[プロフィール案内](profiles/okd-server-modpack/README.md)と[mods.tsv](profiles/okd-server-modpack/mods.tsv)に20個の固定参照があります。WindowsのCurseForgeでインストール・起動・サーバー入場できたとユーザーから報告されています。CIがゲームを実行した結果ではありません。

```bash
python3 -m unittest discover -s tests -v
python3 scripts/local_pack.py --output /tmp/okd-server-modpack-import-preview.zip
```

PR/pushのValidate workflowも同じ草案を生成し、ZIPとSHA256をbuild artifactに保存します。GitHubにログインして対象runのartifactを取得し、artifactの外側のZIPを展開してから、中の `okd-server-modpack-import-preview.zip` をCurseForgeの **Minecraft → Import → Import Profile .zip → Choose .zip file** で指定します。GitHubの **Code → Download ZIP** はリポジトリ全体で、取込用ZIPとは異なります。

草案にはroot manifestと空のoverridesだけが入り、jarやconfigをコピーしません。表示名は `OKD Server Modpack`、slugは `okd-server-modpack` です。版とauthorは草案用の仮値です。この草案は提出用App exportではありません。提出検査は既知の草案identityを拒否しますが、名前を変えた生成ZIPの由来を証明できるわけではありません。

## ZIPを公開する前のローカル検査

1. CurseForge Appで配布専用プロフィールを作り、正式な名前・版・authorに設定して必要なファイルだけexportします。元のプレイ環境を上書きせず、manifestは手編集しません。
2. ZIPの全ファイルを人が確認します。ワールド、ログ、options.txt、servers.dat、個人の地図やサーバー情報、認証情報を除きます。修正が必要なら元プロフィールを直してAppから再exportします。検査やレビューが済むまで外部へアップロードしません。
3. `cp release.example.json release.json` で設定を作り、project ID、export内のMinecraft版・loader ID、表示名、release typeを入力します。公開用ProjectはCurseForgeでユーザーが作成します。`export_asset_id` はこの段階ではnullで構いません。`game_version_names` はMinecraft版、Loader名、Clientの3つです。
4. 内容レビューを済ませたZIPのSHA256を `reviewed_sha256` に記入し、CHANGELOGを書きます。ハッシュだけ更新してレビューを省略しないでください。

```bash
sha256sum /private/path/okd-server-modpack.zip
python3 scripts/release.py --zip /private/path/okd-server-modpack.zip
```

Windowsでは `Get-FileHash -Algorithm SHA256 <ZIPのパス>` でもハッシュを取得できます。`release.py` は既定で通信しないdry-runです。設定・ハッシュ・ZIP構造・プライバシー検査に失敗すれば停止します。成功しても任意の秘密値や配布権をすべて保証するものではありません。再importと動作試験、全内容のレビューを行ってください。

## Release assetを指定する

ローカル検査と公開可否のレビューを終えた正式exportだけを、`aiagate/minecraft-modpack-release` のReleaseへassetとして置きます。Releaseやタグ作成、assetアップロードはユーザーの公開操作です。この準備実装では行っていません。GitにはZIPを追加しません。

asset IDを `release.json` の `export_asset_id` に正の整数として記入します。IDはGitHubのRelease assets APIで確認できます。GitHub CLIを使う場合の読み取り例です。

```bash
gh api repos/aiagate/minecraft-modpack-release/releases/tags/REPLACE_TAG --jq '.assets[] | {id, name}'
```

`reviewed_sha256` はローカルでレビューしたバイトの値を保持します。assetを置き換えるときは、新しいIDとSHA256をレビューして更新します。別リポジトリ、draftや非公開asset、任意URLの取得は扱いません。README・設定・変更履歴・コードをレビューし、Gitへ入れるのはこれらのテキストだけです。`.gitignore` とCIはZIPのGit追跡を防ぎますが、手元の秘密ファイルを安全にするための代替ではありません。

## mainから検証・提出する

GitHub Actionsの **Manual CurseForge submission** をmainで起動します。既定の `submit=false` は、Release assetを取得するGET通信と検証を行いますが、CurseForgeへは提出しません。PR/pushではasset取得も投稿Secret参照も行いません。

preflightは起動時のcommit SHAをcheckoutし、テスト・compileallを実行します。asset IDとサイズを確認し、最大90 MiBまで読み、レビュー済みSHA256とZIP内容を検査してから保存します。検査に失敗したZIPはartifactへアップロードしません。検証済みZIPとreceiptを同一runのartifactに保存し、その正確なartifact IDをsubmit jobへ渡します。

submit jobは同じcommit SHAをcheckoutします。前段のartifact IDが欠けていれば停止し、同じrunのそのartifactだけを取得します。Releaseから再取得せず、受け取ったZIPを同じ設定とSHA256で再検証してから、検証したメモリ内の同一バイトを1回だけ提出します。Artifactを差し替えても期待SHA256との不一致なら停止します。変更されたmain設定や別runのartifactを自動採用しません。

## 投稿Tokenと環境の初回設定

実提出を始めるときだけ、ユーザー自身で設定します。Tokenはチャット、コード、設定、ZIPへ貼り付けないでください。

1. CurseForgeでModPack Projectを作りproject IDを設定します。英語の公開名と説明、400×400の画像などの審査要件も満たします。初回ファイルのAPI受付はこの実装では未検証です。
2. [Authors CurseForge](https://authors.curseforge.com/)のAPI Tokensで投稿用Tokenを発行します。MOD検索用catalog APIキーとは別です。
3. GitHub **Settings → Environments** で `curseforge` を作成し、deployment branchをmainに限定します。必要ならRequired reviewersを設定します。一人で運用する場合、Prevent self-reviewを有効にすると自分では承認できない点を確認してください。
4. environmentのSecret `CURSEFORGE_API_TOKEN` とVariable `CURSEFORGE_SUBMISSION_ENABLED=true` を設定します。未設定では提出を停止します。environment名を書くことだけでは承認ルールは作成されません。[GitHubの環境設定手順](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)を確認してください。
5. dry-runのZIPとreceiptを確認し、mainで `submit=true` を指定します。承認ルールを設定した場合は提出jobの承認が必要です。

write権限のある人はworkflowを書き換えられるため、共同編集者を限定し、main保護とコードレビューも運用に合わせて設定します。

## 受付結果と再実行

receiptはversion、source commit、Release asset ID、ZIP SHA256、project ID、状態、成功時file IDを記録します。TokenやAPI応答本文は記録しません。`validated` は検査成功、`submitted` はAPI受付成功、`submission_unconfirmed` は受付未確認です。API成功は提出済みであり公開済みではありません。`isMarkedForManualRelease=true` を維持するため、審査承認後の公開は作者画面で操作します。

提出先は固定HTTPSホストで、認証はX-Api-Tokenヘッダーだけです。POSTのリダイレクト追従と自動再送はありません。タイムアウト、runner中断、receiptやartifact保存の失敗ではPOSTが成立している可能性があるため、作者画面で受付状況を確認するまで再実行しないでください。concurrencyとcancel-in-progress:falseは同時提出を直列化しますが、手動再実行の重複提出を永続的に防ぎません。

現在の提出トリガーはworkflow_dispatchだけです。将来タグ起動を追加するなら、レビュー済みmain commitへのタグ、タグ保護、環境のタグ許可と版整合性を確認します。サーバーパック提出やMinecraftサーバーへの配置は扱いません。

## 検査の制限

ZIPは展開せず、構造、危険なパス、重複、symlink、暗号化、CRC、サイズ、manifest、Minecraft/Loaderと提出設定を検査します。ローカル方針の上限は圧縮90 MiB・展開256 MiB・1ファイル32 MiB・1万エントリ・圧縮率200倍で、CurseForge公式上限ではありません。

overridesはUTF-8テキストだけを許可し、jar、入れ子アーカイブ、バイナリ、私的情報や接続先らしい記述を拒否します。manifest全体とmodlist.htmlも検査し、modlist内の所定の公開CurseForgeリンクだけを例外として許可します。正当な設定で停止した場合も、manifestを加工して通そうとせず、ファイル・権利・検査方針をレビューしてください。

App生成の真正性、任意の秘密値や難読化、全MODの掲載状態・互換性・配布許可、起動動作は完全には検証できません。testsのmanifestは合成fixtureです。

## 確認した公式仕様

2026-10-06原文確認。

- [CurseForge Upload API](https://support.curseforge.com/support/solutions/articles/9000197321-curseforge-api): metadata/file、認証、版名、受付file ID、手動公開。
- [提出ZIP形式](https://support.curseforge.com/support/solutions/articles/9000198500-exporting-a-modpack-for-curseforge-project-submission): root manifestとoverrides、MOD参照、第三者MODの条件。
- [審査規約](https://support.curseforge.com/support/solutions/articles/9000197279-project-and-modpack-moderation-policies): App作成と生成manifest手編集禁止を明記しています。動的生成ZIPの正式提出は実装しません。
- [GitHub Release assets API](https://docs.github.com/en/rest/releases/assets): asset IDによる公開GET、200/302、IDとサイズ。
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases): Release assetはGitの追跡ファイルとは別に保管されます。
