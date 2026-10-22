# JARECO — JPCOAR Static Catalogue

日本研究・人文学リソースガイドの501件を、PHPやDBなしで検索・閲覧できる実験的な静的サイトです。
英語・日本語の一覧と詳細ページを生成し、ブラウザー内でAND検索・絞り込み・ページ分けを行います。

公開リポジトリ: https://github.com/NIHU-jp/jareco

想定公開先: https://nihu-jp.github.io/jareco/

## 編集と生成

```text
修正版CSV + 補足JSON → 拡張XML → 静的サイト / 交換用JPCOAR XML
```

| ファイル | 役割 |
|---|---|
| [resources.csv](data/resources.csv) | 共同編集へ還流する修正版。元の22列とDrupal IDを保持する編集正本 |
| [supplement.json](data/supplement.json) | 固定IDをキーにする補足正本。publisher・relation・暫定資源タイプ・判断根拠・既存ページID等 |
| [resources.xml](data/resources.xml) | 上記2ファイルから生成するサイト用拡張XML。直接編集しない |
| [csv-corrections.json](data/csv-corrections.json) | 初回CSV修正の変更前後・原本ハッシュ・XMLで省略されていたURL15件の回復記録 |
| [source-build-report.json](data/source-build-report.json) | 現行CSV/JSON/XMLのハッシュと未解決値 |
| [1792652894.csv](data/1792652894.csv) / [1792652897.xml](data/1792652897.xml) | 内容を変更しない保存・提供用原本。通常生成では解析しない |

既存JPCOAR XMLを元にした補正・分類の過去の作業記録はdata/history/に保存しています。
過去のXMLハッシュは当時の状態を指し、現行XMLには対応しません。
元XMLだけにあったpublisher・relation情報は初回移行で補足JSONへ保持しました。

共通の拡張形式と項目の所有ルールは [catalogue_source/README.md](catalogue_source/README.md)、
XML定義は [schema/catalogue.xsd](schema/catalogue.xsd) を参照してください。
6機関DB版も同じ形式・変換コードを使い、サイトの表示方法はそれぞれ維持します。

## ローカルで生成

Python 3.11以上の標準ライブラリで生成可能です（Python 3.14で検証）。

`sh /Users/user/local/nihu.local/repos/jpcoar-static-catalogue/build.sh`

CSV/JSONからdata/resources.xmlを再生成し、dist/へサイトを出力します。CSV/JSONは書き換えません。
XML生成だけならprepare.shです。旧add-ddc.sh/classify.shも現在はprepare.shへの互換入口です。
DDC・分類を変更する際はCSV/JSONを編集してください。tools/の旧XML補正関数は過去作業と検証用です。

`sh /Users/user/local/nihu.local/repos/jpcoar-static-catalogue/preview.sh`

http://127.0.0.1:8894/ を開きます。dist/index.htmlを直接開いても検索できます。

`sh /Users/user/local/nihu.local/repos/jpcoar-static-catalogue/check.sh`

CSVの全フィールド保持、固定ID、CSV変更の反映、補足との競合拒否、原本への非依存、
内部リンク、XMLパーサーを検証し、Node.jsがあれば検索スクリプトも検証します。

## 現行の補正と未確定事項

- 代表URLはCSVの完全な値を使用。元XMLで省略されていた15件を回復しました。
- 元カテゴリを保持し、承認済み大分類DDCを297件に計303個追加。修正版CSVのDDC subject列に格納。
  History→900、Arts and Crafts→700、Religious Studies→200。精密分類ではなくbroadMatchです。
  根拠は [ddc-mapping.json](data/ddc-mapping.json)。既存の数値DDCも保持します。
- HTML実体参照とコンテンツ言語の区切り・en→engを補正。元の値はcsv-corrections.jsonに記録。
- 資源タイプはinteractive resource 485件、dataset 14件、software 2件。補足JSONを現行の編集元とし、
  [resource-type-policy.json](data/resource-type-policy.json)を初回判断の方針として保持します。
- 元のTypes of contentsの9値（8件）は修正版CSVの同列に保持。資源タイプとは別に検索・表示します。
- 「利用条件あり」とコンテンツ言語「その他」は原値をCSV/XML拡張欄に保持し、標準語彙へ推測変換しません。
- 元CSVでURLが空だったID 858/1009は、利用者指定の提供元URLを確認して補完。858は説明が一致する古代版を採用しました。

任意のXSD監査はvalidate.sh（lxmlが必要）。現在501/501件が同梱の標準JPCOAR XSDに適合しています。スキーマ適合は内容の正確性やリンクの将来の有効性を保証するものではありません。
結果は [validation-report.json](data/validation-report.json) にあります。

## 配布物

| URLパス | 内容 |
|---|---|
| original/index.html | 未加工の元CSV・XMLの配布案内 |
| original/1792652894.csv / original/1792652897.xml | 取得時のままの原本 |
| experimental/records.csv | 修正版CSVそのもの。共同編集への還流に使う22列形式 |
| experimental/supplement.json | 修正版CSVに対応する補足情報 |
| experimental/catalogue.xml | 全CSV列と補足を保持する拡張XML |
| experimental/jpcoar.xml | 標準項目のみの交換用加工版。元の収録内容タイプは出自付き説明として保持 |
| experimental/records.json | 検索・表示用の中間JSON |
| experimental/search-records.csv | 検索用投影の簡易CSV。共同編集の正本ではない |
| experimental/build-report.json | XML読取時の件数・ハッシュ・警告 |

以前のexperimental/records.csvは簡易投影でしたが、現在は22列の修正版CSVへ切り替えています。
CSV更新後は変更履歴と確認内容を残し、共同編集先への反映はレビュー後に別途行います。
元データ・修正版・交換用データを混同しないよう、ページ上で区別しています。

## 汎用XML入力・表示

別のJPCOAR XMLを使う場合はsite.tomlのinputを変更し、source_csv/supplementを外してください。
original_input/original_csvも変更または削除します。最小設定はinputだけです。
JPCOAR 1.0/2.0、単一レコード、コレクションラッパー、OAI-PMHの全件スナップショットに対応し、
deletedレコードは除外します。repair_html_entities=trueは既知のHTML実体参照の互換補正用です。
DTDは禁止し、HTMLは表示時にエスケープ、外部リンクは安全なHTTP(S)/DOIだけを採用します。

タイトル・出典・ライセンス・絞り込みはsite.tomlへ分離しています。
絞り込みはsubjects/creators/types/languages/access/content_types。複数条件はANDです。
UIは英語・日本語、データは任意の言語を保持し、自動翻訳はしません。
URLの条件保存と戻る操作に対応し、JavaScriptなしでも全件一覧と詳細を閲覧できます。
固定pageIdは過去の詳細URLを維持し、CSVの名称・URL変更で変わりません。

## GitHub Pages

.github/workflows/pages.ymlが検証・ビルド・公開を行います。Settings → Pages → Sourceを
GitHub Actionsに設定してください。mainへのpushまたは手動実行で公開し、PRでは公開しません。
dist/をコミットせず生成し、リポジトリ名付きサブパスに対応する相対リンクを使用します。

リンク情報の元データはCC0 1.0。全体利用時のResource Guide by NIHU DHへの謝辞は任意です。
リンク先コンテンツには各提供元の利用条件が適用されます。
