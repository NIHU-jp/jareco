# NIHU catalogue profile 1.1

このローカル共通形式は公式NIHU/JPCOAR規格ではありません。名前空間は既存の
`urn:nihu-local:database-catalogue:1` を継続し、JPCOAR 2.0を核に、編集情報を分離します。
`schema/catalogue.xsd` がXML構造を定義します。JPCOARの必須情報が未確定の場合、
生成自体は可能ですがXSD完全適合とは扱いません。

## 編集元と生成物

- 基本CSV: 1行1資源。既存の全列を保持。列の追加・改名には補足JSONのcsv_headersも更新します。
- 補足JSON: profile_version、collection、id_column、csv_headers、catalogue_attributes、
  institutions、records、任意のprovenance。recordsを固定IDで結合します。
- 拡張XML: CSVとJSONから生成。手で変更しません。直接編集可能な第二の正本を作りません。
- 元CSV・元XML: 取得時の保存原本。初回移行後の生成処理は参照しません。

## XML構造

`nihu:catalogue` → 任意件数のinstitutionを持つ`nihu:institutions` + `nihu:supplement` + `nihu:records`。
nihu:supplementは入力補足JSON全体を保持し、由来情報も含めて復元できるようにします。
各`nihu:record`は以下を保持します。

1. `jpcoar:jpcoar`: CSVから対応可能な標準項目＋補足JSONの追加情報。
2. `nihu:administration`: サイト設定・分類判断等のJSON文字列。csv_fieldsはCSVからの生成値です。
3. 任意の`nihu:listSummary`: 言語別の一覧用HTML。
4. `nihu:csvRow source="canonical" row="…"`: 全列を`nihu:field name="列名"`として保持。
   空欄・未知の列の値・非標準語彙も消しません。改行のCRは文字参照で保持します。

recordのidは固定の管理ID、listedは掲載可否、institution/orderは機関と掲載順です。
pageIdは既存の詳細URLを維持するための任意の固定IDで、タイトル・URL変更では変えません。

## 項目の所有と補足JSON

CSVの名称・作成者・説明・アクセス権・代表URL・主題・コンテンツ言語はCSVだけで編集します。
「Japanese Title」と「Original Title」は別列として全値を保持します。Original Titleから言語を
推測しません。Language列はコンテンツ言語と同一視せず、UI言語も独立して保持します。
Types of contentsは収録内容のラベルで、資源そのもののdc:typeとは独立です。
Created Dateを資源の作成日と決めつけません。Related discipline or fieldをe-Rad分類と
推定しません。標準項目に変換できない値もcsvRowに必ず残します。

records[固定ID]の許可キー:
- attributes: XMLレコード属性。CSVのIDとの対応を維持します。
- metadata: CSVにない追加のJPCOAR項目。tag（展開済み名前空間URI）、attributes、text、children
  の構造化JSONです。publisher、追加URL、標準relation等を保持します。生XMLの埋め込みではありません。
- website: 言語別URL選択等。6機関版の日本語代表URLはCSVのResource URLから設定します。
- list_summaries: 言語をキーにした一覧表示用HTML。
- resource_type: valueとuri。JARECOの暫定資源タイプ。
- classification: 判断のbasis、evidence、review_note等。出典と未確定事項を残します。

CSVが担当するスカラー項目をmetadataから上書きすることは拒否します。追加の主題・URL等は
補足できますが、基本CSVに移管した項目はJSON側から除去してください。
未知キー・JSONキー重複・CSVの空ID/重複ID・対応先のない補足ID・未設定の新規IDはエラーです。
新規資源はCSVとJSONへ固定IDを同時に追加します。

## 出力と再現性

CSV内の全フィールド値はcsvRowから復元できます。JPCOARへの射影は一部非可逆ですが、
拡張XMLは編集情報を保持します。補足JSON全体もnihu:supplementに保持します。extract_sourcesで新しいCSV/JSONへ復元でき、
復元先に既存ファイルがあれば上書きを拒否します。
標準だけのJPCOARは外部交換用であり、サイト再生成や共同編集用の完全な代替ではありません。
URIに不適切な文字はXMLの標準identifierでパーセントエンコードし、CSVの値は変更しません。
未対応のアクセス権・言語は標準値を推測せず、ローカル欄とsource-build-reportの警告に残します。

両独立リポジトリは同じcatalogue_sourceコードとcatalogue.xsdを同梱します。
リポジトリ間の実行時依存はありません。共通処理を変えたら双方へ同期し、双方のテストを実行します。
