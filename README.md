# JPCOAR Static Catalogue

JPCOAR XMLから、一覧・検索・絞り込み・個別詳細ページを持つ静的サイトを生成します。検索はブラウザー内で完結し、PHP・DB・検索API・外部CDNを必要としません。GitHub Pagesのリポジトリ名付きURLでも使える相対リンクで生成します。

同梱の実データは、NIHU Resource Guideの保存ファイル `1792652897.xml`（501件）を補正した [data/resources.xml](data/resources.xml) です。この修正済みXMLを編集・生成の正本にし、原本は出典として保持します。ジェネレーターに機関コードや固定カテゴリを埋め込まず、コレクション固有の表示・出典・ライセンスは [site.toml](site.toml) に分離しています。

## 生成とプレビュー

Python 3.11以上の標準ライブラリだけで生成できます。このプロジェクトではPython 3.14で検証しています。追加のPythonパッケージやNode.jsのビルド依存はありません。

ローカル生成:

`sh /Users/user/local/nihu.local/repos/jpcoar-static-catalogue/build.sh`

`dist/` に生成します。`dist/index.html` を直接開いても検索できます。HTTPでのプレビュー:

`sh /Users/user/local/nihu.local/repos/jpcoar-static-catalogue/preview.sh`

起動後に <http://127.0.0.1:8894/> を開きます。ポートは `JPCOAR_PREVIEW_PORT` で変更できます。別の場所にクローンした場合は、上記コマンドのリポジトリへのパスを置き換えてください。

検証:

`sh /Users/user/local/nihu.local/repos/jpcoar-static-catalogue/check.sh`

Pythonによるパーサー・生成物・内部リンクの検証に加え、Node.jsがあれば標準のテストランナーで実際の検索スクリプトも検証します。CIでは両方を実行します。

## 閲覧・検索

- 英語・日本語の画面。データ自体は言語を問わず検索し、名称・別名・説明・作成者・その他のメタデータを対象にします。
- 空白で区切った複数語はAND検索。全角半角と英字大小を正規化した部分一致です。語形解析・曖昧検索・検索順位付けは行いません。
- 主題・作成者／提供元・資源タイプ・資料言語・アクセス権・元データの収録資料タイプの絞り込み。複数の条件はAND、各条件は完全一致です。
- 絞り込み候補の括弧内の数はコレクション全体の件数です。検索後の動的な件数ではありません。
- 検索条件・絞り込み・ページ番号をURLに保存し、共有やブラウザーの戻る操作に対応します。
- 詳細ページはすべて事前生成します。JavaScriptがなくても全件の一覧と詳細を閲覧できます。
- 英語画面では英語、和文画面では日本語の名称を優先し、なければ元の名称を表示します。言語不明の値を自動翻訳・自動判定しません。
- 外部リンクがないレコードも除外しません。リンクの生存確認はビルド中に行いません。

データは検索用に全件をページへ埋め込むため、検索時に外部通信しません。数百～数千件程度の利用を想定しています。非常に大きな説明文や数万件以上のコレクションでは、転送量とDOM数を測定し、索引分割等の追加実装を検討してください。

## 別のJPCOAR XMLへ差し替える

1. XMLを `data/` 等に置きます。`site.toml` の `input` を変更します。パスは設定ファイルからの相対パスです。
2. `[title]`・`[description]`・`[notice]`・`[source]`・`[license]` をそのコレクションに合わせて変更します。ライセンスは自動でCC0になりません。
3. `default_language`、`languages`、`facets`、`page_size` を必要に応じて変更します。UI言語は現在 `en` と `ja`。メタデータ自体は任意の言語を保持できます。
4. `sh build.sh` で再生成します。独自設定は `sh build.sh --config /absolute/path/site.toml --output /absolute/path/site` のように指定できます。

最小設定は `input = "data/example.xml"` の1項目だけです。省略時は英語UI・全6種の絞り込み・20件ずつ表示になります。生成後の `dist/` を直接編集せず、データ・設定・ジェネレーター側を変更してください。

設定で有効にできる絞り込みは `subjects`・`creators`・`types`・`languages`・`access`・`content_types` です。creatorはJPCOARの作成者を表示しており、あらゆるデータでホスティング機関を意味するわけではありません。`HostingInstitution` や独自の機関区分からの推定は行っていません。

## 対応範囲と入力の扱い

- JPCOAR 1.0 / 2.0の公式名前空間URIを認識し、接頭辞名に依存しません。
- 単一の `jpcoar:jpcoar`、`ListRecords/record/metadata`、OAI-PMHレスポンス、その他のコレクション用ラッパー内のレコードを読み取れます。
- OAI-PMHのdeletedレコードは公開対象から除外します。差分ハーベスト、resumptionTokenの自動取得、過去データとのマージは行いません。**公開したい全件を含むスナップショット**を入力してください。
- 主な抽出項目は `dc:title`、`dcterms:alternative`、DataCiteのdescription、JPCOARのcreator・publisher・subject・identifier、`dc:publisher/type/language`、`dcterms:accessRights`。DataCite kernel-3/4のhttp/https名前空間と、今回のエクスポートにある非標準の `lang` 属性も読み取ります。
- 上記以外のフィールドも、階層名とプレーンテキストで詳細・検索用データに保持します。全JPCOAR項目の意味に応じた専用UIを持つわけではありません。包含関係も自動で階層表示しません。
- **XSDに対する適合性検証器ではありません。** 今回の元データにも属性不足等があるため、XML構文解析と表示に必要な項目の抽出を分けています。
- OAI識別子があればそれを元に詳細URLを生成します。なければ名称・作成者・識別子のハッシュを使います。後者ではこれらの編集により詳細URLが変わります。同じ識別情報の重複は削除せず連番を付けて警告します。
- HTTP(S)のみをリンクとして採用し、明示的なDOI識別子は `https://doi.org/` に変換します。元の値はメタデータに残します。`javascript:`・相対URL・認証情報付きURL等はリンクにしません。
- 入力内のHTMLをそのまま実行しません。表示はエスケープし、検索用JSONもスクリプト要素を閉じられない形で埋め込みます。DTD・エンティティ宣言は拒否します。

### 同梱データの修正

利用者の許可に基づき、原本を保持したまま `data/resources.xml` を修正済みの正本にしました。現在の設定では互換補正を有効にせず、修正済みXMLを厳格に構文解析します。

- 未定義の `&nbsp;` 1か所をXMLで扱える文字に修正。
- 非標準の `lang` 315か所を `xml:lang` に変更。
- 説明文315か所の必須 `descriptionType` に、内容を過度に分類しない `Other` を設定。
- HTTP(S)識別子499か所に `identifierType="URI"` を付与。
- サイト独自の英語カテゴリ512か所に誤って付いたDDC指定を `Other` に修正。数値のDDC分類は保持。
- URLだけが入った関連情報7か所を `relatedIdentifier` に格納。関係の種類は推測しません。
- 490レコードの要素を公式スキーマの順序に並べ替え。
- 資料言語3か所を補正。`jpn, eng` は要素を分け、`en` は `eng` に変更。

各修正の対象・変更前後・ハッシュと未解決項目は [data/corrections.json](data/corrections.json) に記録しています。名称・作成者・説明本文・URLの情報を保持する検証も行っています。外部URLなし2件は除外していません。

### 元カテゴリを残したDDCの追加

元サイトのカテゴリは `subjectScheme="Other"` として残し、利用者が承認した3カテゴリに限ってDDCの大分類を追加しています。

| 元カテゴリ | 追加DDC | 追加主題数 |
|---|---|---:|
| History | 900 | 131 |
| Arts and Crafts | 700 | 150 |
| Religious Studies | 200 | 22 |

297レコードに計303個を追加しました。複数カテゴリを持つレコードには対応するDDCも複数付きます。元からあった数値DDC（例：708）も変更しません。

これは [OCLCのDDC概要・第1要約](https://www.oclc.org/content/dam/oclc/dewey/resources/summaries/deweysummaries.pdf)（DDC第22版、2003年、PDFの9ページ目）を参照した、サイトカテゴリから大分類への `broadMatch` です。資料単位の精密な分類や同義語への置き換えではありません。例えばHistoryの対応先900は地理も含む、より広い分類です。

[data/ddc-mapping.json](data/ddc-mapping.json) に対応表・根拠・未対応カテゴリと理由を、[data/ddc-assignments.json](data/ddc-assignments.json) に各レコードへの付与とハッシュを記録しています。文学と言語学などの複合カテゴリ、資料の所在・形態によるカテゴリ、汎用的すぎるカテゴリには追加しません。

再適用は次のスクリプトで行えます。既存のDDCは削除せず、同じ入力と対応表での再実行はXMLも履歴も変更しません。対応表を改訂して過去の付与を撤回したい場合は、既存値の由来を確認して別途修正してください。

`sh /Users/user/local/nihu.local/repos/jpcoar-static-catalogue/add-ddc.sh`

### 実験的な資源タイプの付与と配布の分離

利用者と合意した暫定方針として、レコードが紹介する資源そのものを分類します。オンラインデータベース・一般のWebページ等は `interactive resource`（485件）、独立して配布されると判断できるデータを `dataset`（14件）、ツールを `software`（2件）としました。全Webページが公式語彙の定義に厳密に合致するという主張ではなく、この実験用データの既定分類です。不確実な候補は既定分類に置き、見直し理由を記録しています。

方針・例外・出典は [data/resource-type-policy.json](data/resource-type-policy.json)、各501件の判断とハッシュは [data/resource-type-assignments.json](data/resource-type-assignments.json) にあります。再適用は `sh classify.sh`。同じ入力と方針ではXMLと履歴を変更しません。

元の `dc:type` 9値（8レコード）は削除せず、record直下の `sc:contentType`（名前空間 `urn:jpcoar-static-catalogue:1`）に保持します。これらは元の入力ラベルであり、収録資料の形態をすべて再調査した結果ではありません。画面・検索・JSON・CSVでは資源タイプと別項目とし、交換用 `experimental/jpcoar.xml` には元フィールドを明記した `descriptionType="Other"` の説明へ転記します。

`site.toml` の任意設定 `original_input` で未加工の元XMLを指定すると、専用の `original/` 配布ページを生成します。元データの不整合も含めバイト単位で保持し、解析し直しません。実験的SSGとその加工版XML・CSV・JSONは `experimental/` にまとめ、案内・ダウンロードとも区別します。他の入力へ差し替える際は `original_input` も変更するか削除してください。正式版の更新や公式な分類見直しとしては扱いません。

### 残るスキーマ不適合

**加工版XMLも、完全なJPCOAR 2.0適合データではありません。** 現在493/501件が同梱XSDに適合し、8件に識別子の欠落2件・URIの不整合4件・言語「その他」1件・アクセス権「利用条件あり」1件が残ります。URIの不整合には省略されたURLや未エスケープの波括弧等が含まれます。スキーマ適合だけを目的に、欠けたリンク先や意味を推測補完しません。サイト生成成功とXSD適合を区別してください。

公式XSDを [schema/](schema/) に同梱し、任意のオフライン監査を行えます。監査にはlxmlが必要ですが、通常ビルドの依存には加えていません。

`sh /Users/user/local/nihu.local/repos/jpcoar-static-catalogue/validate.sh`

監査結果を [data/validation-report.json](data/validation-report.json) に保存します。不適合が残れば終了コード1を返します。未解決のため現状の監査は成功扱いにしていません。`check.sh` はサイト生成・検索の検証であり、完全なXSD適合を保証しません。

ジェネレーター自体には、別の既存エクスポートを扱うための `repair_html_entities = true` オプションを残しています。既知のHTML名前付き実体参照だけを数値文字参照に変換するUTF-8入力用の機能で、CDATA・コメントは変更しません。通常は省略して厳格なXML解析を使ってください。

## 生成されるデータ

| ファイル | 内容 |
|---|---|
| `original/index.html` | 元XML専用の日英配布案内。実験サイトと分離 |
| `original/1792652897.xml` | 元サイトのXMLをバイト単位で変更せず複製 |
| `experimental/catalogue.xml` | 実験用のビルド入力XML。独自の収録資料タイプを含む加工版 |
| `experimental/jpcoar.xml` | JPCOAR要素をListRecords形式で包んだ交換用加工版。独自の収録資料タイプは明示した説明文へ転記。XSD適合は未完了 |
| `experimental/records.json` | 多言語・フィールドを保持した表示用の中間データ |
| `experimental/records.csv` | 名称・説明・作成者等の固定列による簡易CSV。複数値は ` | ` 区切り。元のDrupal CSV形式とは異なります |
| `experimental/build-report.json` | 件数・実行時の互換補正・警告・ビルド入力のSHA-256 |

CSVの式として扱われ得る値には、スプレッドシートでの誤実行を避けるため先頭にアポストロフィを付けます。厳密な再利用には元XML・JPCOAR XMLまたはJSONを使ってください。

## GitHub Pages

公開先リポジトリ: [NIHU-jp/jareco](https://github.com/NIHU-jp/jareco)

想定公開URL: <https://nihu-jp.github.io/jareco/>（Pages設定・デプロイ完了後）。ページ末尾にもこのURLを掲載しています。

[GitHub公式のカスタムワークフロー手順](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)に沿った `.github/workflows/pages.yml` を同梱しています。

1. この独立リポジトリをGitHubに作成・pushし、既定ブランチを `main` にします。
2. Settings → Pages → Build and deployment → Sourceで **GitHub Actions** を選びます。
3. `main` へのpushまたは手動実行で、検証→ビルド→Pages公開が動きます。Pull Requestでは検証とビルドだけを行います。

公開するのは `dist/` だけです。コード・設定・入力データをリポジトリで公開することとは別なので、別データへ差し替えるときは公開可能なデータだけを入力してください。元サイトの停止判断を変更したり、元サーバーへアクセスしたりする機能はありません。

## 出典と権利

同梱データは [NIHU Resource Guide](https://guides2.nihu.jp/) の [Download for Links](https://guides2.nihu.jp/downloads) でCC0 1.0として提供されているリンク情報です。2026-10-22に手元へ保存されたファイルを使用しています。リンク先のコンテンツの権利は各提供元に帰属します。元の案内に従い、コレクション全体の利用時にはResource Guide by NIHU DHへの任意の謝辞をお願いします。

データの利用条件は設定ファイルに記録し、別コレクションへ自動継承しません。元サイトのロゴやテーマは使用していません。ジェネレーター自体のライセンスはまだ設定していません。
