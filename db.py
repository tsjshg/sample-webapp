
import sqlite3
from typing import ClassVar
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

# データベースのファイル名
DATABASE_FILE = "estore.db"

class OrderStatus(Enum):
    '''注文状態を管理する定数
    '''
    ORDER = 0 # 注文だけされて出荷待ち
    SHIP = 1 # 出荷済み

class DataBase:
    '''データベースへの接続を保持するクラス
    データベースにはすでにテーブルが正しく作成されていることを前提とします。
    '''

    def __init__(self):
        self.con = sqlite3.connect(DATABASE_FILE)
        # 検索結果をRow型で返すための設定
        # そのままクラスの初期化メソッドへ渡せます
        # これを書かないとデータベースからはタプルで返ります
        self.con.row_factory = sqlite3.Row

class Entity:
    '''データベースの1つのテーブルに対応した抽象クラス
    '''

    def __init__(self, table_name):
        ''' 具象子クラスから呼び出してください

        Parameters
        ----------
        table_name: str
            このクラスに対応したテーブルの名前
        '''
        self.table_name = table_name
    
    @classmethod
    def all(cls, engine, where=""):
        ''' テーブルにあるすべての行を読み込みインスタンスを生成して返すクラスメソッド
        
        Parameters
        ----------
        engine: DataBase
            データベースへの接続を保持するDataBase型のインスタンス
        where: str
            そのままwhere句の場所へ入れる

        Returns
        -------
        results: list
            全てのインスタンスを格納したリスト。インスタンスが無い場合は空のリストを返す。
        '''
        # 全てのテーブルにid列がある前提
        sql = f"select * from {cls.table_name} {where} order by id"
        results = []
        for row in engine.con.execute(sql):
            # 検索結果からクラスのインスタンスを生成
            results.append(cls(**row))
        return results

    @classmethod
    def get(cls, primary_key, engine):
        ''' 主キーに設定されているid列のインスタンスを取得します。
        
        Parameters
        ----------
        primary_key: int
            主キー
        engine: DataBase
            データベースへの接続を保持するDataBase型のインスタンス

        Returns
        -------
        results: 該当するクラスのインスタンス
            エラーが起きた場合や、該当するインスタンスが無い場合は、Noneを返します（それでいいのか？）
        '''
        sql = f"select * from {cls.table_name} where id = {primary_key}"
        try:
            cur = engine.con.execute(sql)
            results = cls(**cur.fetchone())
        except: # 該当する行が存在しない場合は、TypeError
            results = None
        return results

    def insert(self, engine):
        ''' （要検討）insert成功後、PKのidを返すかどうか。
        '''
        raise NotImplementedError("具象子クラスで実装してください。")

    def update(self, engine):
        raise NotImplementedError("具象子クラスで実装してください。")

    def delete(self, engine):
        raise NotImplementedError("具象子クラスで実装してください。")

@dataclass
class Product(Entity):
    '''商品を表現するクラス 
    '''
    table_name: ClassVar[str] = "product"
    id: int
    name: str
    info: str
    price: int
    stock: int

    def update(self, engine):
        '''既存レコードを更新する
        '''
        with engine.con as con:
            con.execute("UPDATE product SET name=?, info=?, price=?, stock=? where id=?", (self.name, self.info, self.price, self.stock, self.id))

@dataclass
class Order(Entity):
    '''注文を表現するクラス
    '''
    table_name: ClassVar[str] = "orderlist"
    product_id: int
    num: int
    customer_name: str
    customer_email: str
    customer_address: str
    id: int = 0
    status: int = OrderStatus.ORDER.value

    def insert(self, engine):
        '''注文が確定される時に実行されるメソッド
        orderテーブルに1行挿入し、注文された商品の在庫を減らす
        '''
        # この記述でコンテキストマネージャによるcommitとrollbackの機能が正しく実行されるか？
        # ほんとはもっときちんとトランザクション処理を考えないとダメだと思う。
        with engine.con:
            # 売れた商品の読み込み
            product = Product.get(self.product_id, engine)
            # 注文を書き込む
            engine.con.execute("insert into orderlist(product_id, num, customer_name, customer_email, customer_address, status) values(?, ?, ?, ?, ?, ?)", (self.product_id, self.num, self.customer_name, self.customer_email, self.customer_address, self.status))
            # 在庫の減少
            # numがformから読み込んだので、intではないという点については、ちょっと根本的な改良の余地がありますね。
            product.stock -= int(self.num)
            product.update(engine)

    def update(self, engine):
        '''注文の状態を変更する
        '''
        with engine.con as con:
            con.execute("UPDATE orderlist SET product_id=?, num=?, customer_name=?, customer_email=?, customer_address=?, status=? where id=?", (self.product_id, self.num, self.customer_name, self.customer_email, self.customer_address, self.status, self.id))

    def delete(self, engine):
        '''このインスタンスをデータベースから削除
        '''
        with engine.con as con:
            con.execute("DELETE from orderlist where id = ?", (self.id, ))

    def cancel(self, engine):
        '''この注文をキャンセルする
        商品在庫を戻して、orderlistテーブルから削除する
        '''
        with engine.con as con:
            product = Product.get(self.product_id, engine)
            # 在庫を戻す
            product.stock += int(self.num)
            product.update(engine)
            # この注文を削除する
            self.delete(engine)
            # トランザクション処理がー、と思ったりはしますが、ひとまずこれでいいかなと。


def init_table(force=False):
    ''' データベースを初期化する便利関数
    商品（product）と注文（order）のテーブルを作り、商品のサンプルデータを書き込みます。

    Parameters
    ----------
    force : bool
        Trueにするとファイルがあっても強制的に初期化します。ファイルがない場合はこの引数は無視されます。
    '''
    # ファイルのチェック
    p = Path(DATABASE_FILE)
    if p.exists() and not force:
        # すでにあるのでなにもしない
        return
    # データベースへ接続
    con = sqlite3.connect(DATABASE_FILE)
    # 商品テーブルの作成
    con.execute('''
        CREATE TABLE "product" (
        "id"	INTEGER NOT NULL UNIQUE,
        "name"	TEXT NOT NULL,
        "info"	TEXT,
        "price"	INTEGER,
        "stock"	INTEGER,
        PRIMARY KEY("id" AUTOINCREMENT))
    ''')
    # 注文テーブルの作成
    con.execute('''
        CREATE TABLE "orderlist" (
        "id"	INTEGER NOT NULL UNIQUE,
        "product_id"	INTEGER NOT NULL,
        "num"	INTEGER NOT NULL,
        "customer_name"	TEXT NOT NULL,
        "customer_email"	TEXT,
        "customer_address"	TEXT,
        "status"	INTEGER,
        FOREIGN KEY("product_id") REFERENCES "product"("id"),
        PRIMARY KEY("id" AUTOINCREMENT))
    ''')
    # 商品サンプルのinsert
    con.execute("insert into product(name, info, price, stock) values('USB-M-16G', '16GB USBメモリー', 1200, 400)")
    con.execute("insert into product(name, info, price, stock) values('皮の財布', 'お金が増える緑色', 80000, 20)")
    con.execute("insert into product(name, info, price, stock) values('クマのぬいぐるみ', '体長2m、体重4kg', 9800, 100)")
    con.execute("insert into product(name, info, price, stock) values('自転車', '後ろにカゴあり', 50000, 4)")
    con.execute("insert into product(name, info, price, stock) values('フライパン', '一生使えるステンレス製', 12000, 60)")
    # コミットして接続を閉じる
    con.commit()
    con.close()

if __name__ == "__main__":
    # データベースの初期化
    init_table()
    # テスト
    engine = DataBase()
    print(Product.get(10, engine))