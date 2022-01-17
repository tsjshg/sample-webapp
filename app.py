
# 標準ライブラリ
import os
# 外部ライブラリ
from bottle import template, static_file, request, get, post, run, view
# 自作ライブラリ
import db


@get('/js/<filename>')
def static_js(filename):
    '''JavaScriptで作られた静的なファイルを配信するための関数
    '''
    return static_file(filename, root='./honoka/js')

@get('/css/<filename>')
def static_css(filename):
    '''CSSで作られた静的なファイルを配信するための関数
    '''
    return static_file(filename, root='./honoka/css')

@get('/img/<filename>')
def static_img(filename):
    '''画像ファイル配信用
    '''
    return static_file(filename, root='./images')

# GETメソッドで呼ばれる
@get("/")
# テンプレートの指定（以下の関数でも同様です）
@view("index")
def index():
    '''お客さんが見るトップページの表示
    '''
    # テンプレートへ流し込むためのデータを辞書型で用意（以下の関数でも同様です）
    res = {}
    # 全商品をデータベースから読み込む
    res["products"] = db.Product.all(engine)
    res["title"] = "ようこそ！よろず屋へ"
    return res

# POSTメソッドで呼ばれる
@post("/buy")
@view("order_page")
def buy():
    '''購入受け付けページへ
    '''
    # お客さんが選んだ商品IDと個数を受け取る
    item_id = request.forms.get('item-id')
    num = int(request.forms.get('num'))
    res = {}
    res['title'] = '購入申し込み'
    # 商品情報の読み込み
    item = db.Product.get(item_id, engine)
    res['item'] = item
    res['num'] = num
    # 合計金額を計算して表示用に格納
    res['total'] = f"{item.price * num:,}"
    return res

@post("/confirm")
@view("thanks")
def confirm():
    '''購入完了を表示する画面
    '''
    order = db.Order(**request.forms)
    # 文字化けを回避するため（これは本質的な意味はありません。別の根本的な解決策がありそう・・・。）
    order.customer_name = request.forms.customer_name
    order.customer_address = request.forms.customer_address
    # 注文をデータベースへの書き込み
    order.insert(engine)
    res = {"title": "確認ページ"}
    # お客さんの名前を画面に表示
    res['name'] = order.customer_name
    return res

@get("/admin/order")
@view("admin_order")
def get_admin_order():
    '''注文管理ページ
    '''
    res = {}
    res['title'] = "注文管理ページ"
    # すべての注文を読み込む
    res['orders'] = db.Order.all(engine)
    return res

@post("/admin/order")
@view("admin_order")
def admin_order():
    '''注文を処理して注文管理ページを表示する

    - 出荷待ちのものを出荷済みにする
    - 注文のキャンセル処理
    '''
    # 該当する注文の読み込み
    order = db.Order.get(request.forms.order_id, engine)
    command = request.forms.command
    if command == 'ship':
        # 出荷処理　Order.statusを変更してレコードを更新
        order.status = db.OrderStatus.SHIP.value
        order.update(engine)
    else: # キャンセル処理
        order.cancel(engine)
    # 一覧表示画面へ
    return get_admin_order()

@get("/admin/stock")
@view("admin_stock")
def get_admin_stock():
    '''在庫管理ページ
    '''
    res = {}
    # 全商品をデータベースから読み込む
    res["products"] = db.Product.all(engine)
    res["title"] = "在庫管理ページ"
    return res

@post("/admin/stock")
@view("admin_stock")
def admin_stock():
    '''在庫の数を変更して、在庫管理ページを表示する
    '''
    product = db.Product.get(request.forms.item_id, engine)
    product.stock = int(request.forms.stock)
    product.update(engine)
    return get_admin_stock()

if __name__ == "__main__":
    # データベースの初期化
    db.init_table()
    # グローバル変数にデータベースを登録（別の設計を考えることもできると思います。）
    engine = db.DataBase()
    with engine.con:
        # ポート番号はここで変更可能
        run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)) , reloader=True , debug = True)
