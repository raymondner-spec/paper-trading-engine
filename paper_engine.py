from flask import Flask, request, jsonify
from sqlalchemy import create_engine, Column, Integer, Float, String
from sqlalchemy.orm import declarative_base, sessionmaker
import os

app = Flask(__name__)

# Database setup
DATABASE_URL = "sqlite:///paper_trading.db"
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)
Base = declarative_base()

# Models
class Account(Base):
    __tablename__ = "account"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    cash = Column(Float, default=100000)
    equity = Column(Float, default=100000)
    realized_pnl = Column(Float, default=0)

class Position(Base):
    __tablename__ = "position"
    id = Column(Integer, primary_key=True)
    account = Column(String)
    symbol = Column(String)
    qty = Column(Float, default=0)
    avg_price = Column(Float, default=0)

class Trade(Base):
    __tablename__ = "trade"
    id = Column(Integer, primary_key=True)
    account = Column(String)
    action = Column(String)
    symbol = Column(String)
    qty = Column(Float)
    price = Column(Float)
    pnl = Column(Float)

Base.metadata.create_all(engine)

# Helpers
def get_account(session, name):
    acc = session.query(Account).filter_by(name=name).first()
    if not acc:
        acc = Account(name=name)
        session.add(acc)
        session.commit()
    return acc

def get_position(session, account, symbol):
    pos = session.query(Position).filter_by(account=account, symbol=symbol).first()
    if not pos:
        pos = Position(account=account, symbol=symbol)
        session.add(pos)
        session.commit()
    return pos

# Routes
@app.route("/health")
def health():
    return jsonify({"ok": True})

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("Received:", data)

    session = Session()

    account_name = data["account"]
    action = data["action"]
    symbol = data["symbol"]
    qty = float(data["qty"])
    price = float(data["price"])

    acc = get_account(session, account_name)
    pos = get_position(session, account_name, symbol)

    pnl = 0

    if action == "buy":
        if pos.qty < 0:
            pnl = (pos.avg_price - price) * abs(pos.qty)
            acc.cash += pnl
            acc.realized_pnl += pnl
            pos.qty = 0

        new_qty = pos.qty + qty
        pos.avg_price = ((pos.avg_price * pos.qty) + (price * qty)) / new_qty if pos.qty > 0 else price
        pos.qty = new_qty

    elif action == "sell":
        if pos.qty > 0:
            pnl = (price - pos.avg_price) * pos.qty
            acc.cash += pnl
            acc.realized_pnl += pnl
            pos.qty = 0

        pos.qty -= qty
        pos.avg_price = price

    elif action == "close_long" and pos.qty > 0:
        pnl = (price - pos.avg_price) * pos.qty
        acc.cash += pnl
        acc.realized_pnl += pnl
        pos.qty = 0

    elif action == "close_short" and pos.qty < 0:
        pnl = (pos.avg_price - price) * abs(pos.qty)
        acc.cash += pnl
        acc.realized_pnl += pnl
        pos.qty = 0

    acc.equity = acc.cash

    trade = Trade(
        account=account_name,
        action=action,
        symbol=symbol,
        qty=qty,
        price=price,
        pnl=pnl
    )

    session.add(trade)
    session.commit()
    session.close()

    return jsonify({"status": "ok"})

@app.route("/account/<name>")
def account_view(name):
    session = Session()
    acc = get_account(session, name)
    pos = session.query(Position).filter_by(account=name).all()

    return jsonify({
        "cash": acc.cash,
        "equity": acc.equity,
        "realized_pnl": acc.realized_pnl,
        "positions": [
            {"symbol": p.symbol, "qty": p.qty, "avg_price": p.avg_price}
            for p in pos
        ]
    })

# Railway-compatible run
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)