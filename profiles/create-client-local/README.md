# Create Client Local Draft

Minecraft Java Edition **1.21.1**、NeoForge **21.1.250**、MOD **20個**のクライアント構成です。名称と版は仮で、正式な公開名は未設定です。[mods.tsv](mods.tsv)に正確なファイル名、projectID/fileID、公式配布ページ、Environmentとライセンス表示を記録しています。[manifest.json](manifest.json)はその20個を固定したローカル再現用の参照表です。

## Windowsで生成済みZIPを取り込む

[取込用ZIPをダウンロード](https://github.com/aiagate/minecraft-modpack-release/raw/refs/heads/feature/create-client-reconstruction-20261006/downloads/create-client-local-draft.zip)し、CurseForgeの **Minecraft → Import → Import Profile .zip → Choose .zip file** でそのZIPを選びます。[公式手順](https://support.curseforge.com/support/solutions/articles/9000198501-exporting-and-importing-modpacks)では新しいプロフィールとして作成されます。既存のプロフィールフォルダへ展開したり、設定をコピーして上書きしたりする必要はありません。取込後にMinecraft 1.21.1 / NeoForge 21.1.250 / MOD 20個を照合します。

GitHubの **Code → Download ZIP** はリポジトリ全体のアーカイブです。そのままImportせず、このページの取込用ZIPを使ってください。GitHubのファイル画面で取得する場合は、ZIPファイルの **Download raw file** を選びます。CI artifactやGitHub Releaseとしての配布は行っていません。

ZIPは718 bytesで、SHA256は `048948e98b66f9d2057475e3f16027425700087251dab46f6054d085ed20d455` です。小さいのはMOD jarを含めず、CurseForge上の20個のファイルをmanifestで参照するためです。CIでは再生成バイトとの一致も確認します。取込と起動は未確認です。

## CurseForge Appで構成を手動再現する

1. Minecraft 1.21.1 / NeoForge 21.1.250の新しいプロフィールを作ります。
2. mods.tsvの20個を、それぞれ指定された版で追加します。最新の版へ置き換えず、ファイル名とfileIDを照合してください。
3. 全20個、Minecraft、NeoForgeの版を確認し、別プロフィールで起動と動作を確認します。

必要ならリポジトリのルートで、ローカル取込用ZIPを生成できます。Python 3.12以降の標準ライブラリだけを使用し、ネットワーク通信はありません。

```bash
python3 scripts/local_pack.py --output /tmp/create-client-local-draft.zip
```

出力はrootの `manifest.json` と空の `overrides/` のみです。CurseForgeのImportで使う形式の草案ですが、Appへの実際の取込は未検証です。生成処理はMODのダウンロードや実行をしません。生成ZIPを正式export用の `packs/` に置かないでください。`downloads/` の固定草案とSHA256はこの生成処理の結果で、構成変更時は両方を更新してCIの一致確認を通します。

## 確認できたことと残る確認

2026-10-06時点で、全20件の公式CurseForgeファイルページのファイル名、Minecraft版、NeoForge、projectID/fileIDを照合しました。構成と参照表の整合性はCIで確認します。ファイルの掲載状態や互換性をCIがオンラインで確認するわけではありません。

- ゲーム起動、20個の実ダウンロード、サーバー接続、独自設定との一致は未確認です。参照構成にconfig/defaultconfigsはなく、設定を推測して追加していません。
- Inventory Profiles NextとlibIPNは公式EnvironmentがClientです。CreateとRefined StorageはNot Set、残り16件はClient & Serverです。これはクライアント構成であり、同じ20個をそのままサーバーへ入れる手順ではありません。
- Flywheel/Ponder、FlightLib、Common Networkingなどは指定jarに同梱されるため、別の版を追加していません。jar内ライブラリの再帰的な依存版・ロード順やゲーム内の動作は未検証です。
- Create: Stuff & Additionsの指定ファイルはBetaです。Mechanical Extruderはファイル名2.2.2に対し、内部版が1.21.1-2.2.1-6.0.10です。指定ファイルを保持しています。
- 全件のCurseForge取得バイトとのハッシュ一致は未検証です。JEIのみ、作者の公式Maven成果物との一致を確認しました。

## JEIは指定NeoForgeの互換処理で依存判定を通る

[JEI 19.51.0.418のNeoForgeファイル](https://www.curseforge.com/minecraft/mc-mods/jei/files/8792638)はMinecraft 1.21.1向けです。内部の `META-INF/neoforge.mods.toml` はMinecraft必須依存に `[1.21, 1.21.1)` を指定します。通常のMaven範囲では1.21.1を除外しますが、指定NeoForgeではこれだけで不適合にはなりません。

[NeoForge 21.1.250の公式POM](https://maven.neoforged.net/releases/net/neoforged/neoforge/21.1.250/neoforge-21.1.250.pom)が指定するFMLは4.0.44です。[FML 4.0.44の公式ソース](https://maven.neoforged.net/releases/net/neoforged/fancymodloader/loader/4.0.44/loader-4.0.44-sources.jar)の `VersionSupportMatrix` は、Minecraft 1.21.1で通常の依存判定が失敗した際に1.21も互換候補として判定します。`ModSorter` がこの処理を使い、1.21はJEIの宣言範囲内なので合格します。これは指定版のコードを読んだ静的判断で、実際の起動結果ではありません。別版への置換は行っていません。

JEIの範囲は未展開の変数ではなく、[公式タグv19.51.0の設定](https://github.com/mezz/JustEnoughItems/blob/78ca55a5db926f8f3bc4a3c8d250ffad18cbb806/gradle.properties)でも同じ値です。指定構成のJEIと[作者の同版Maven成果物](https://maven.blamejared.com/mezz/jei/jei-1.21.1-neoforge/19.51.0.418/jei-1.21.1-neoforge-19.51.0.418.jar)のSHA256は `8bc3936d869e4040a5649c58b7e8be1c78c82a245c0dc07bdd68ab49121a222c` で一致しました。jarそのものはこのリポジトリに収録しません。

## 配布と正式提出

全20個はCurseForgeのファイルIDで参照します。第三者jarは直接再配布しません。mods.tsvのライセンス欄は公式Projectの表示を記録したもので、パック全体へのライセンス付与や直接再配布許可を意味しません。All Rights ReservedやCustom LicenseのMODも含まれます。

このmanifestは手で組み立てた再現資料で、公開提出用のApp exportではありません。[CurseForgeの提出規則](https://support.curseforge.com/support/solutions/articles/9000197279-project-and-modpack-moderation-policies)はAppで作成した正しい形式を要求し、生成manifestの手編集を許可していません。提出する際はApp上で構成と動作を確認し、[正式export](https://support.curseforge.com/support/solutions/articles/9000198501-exporting-and-importing-modpacks)を生成して、ルートREADMEの提出手順へ進みます。プロジェクト作成・アップロード・公開提出は未実施です。
