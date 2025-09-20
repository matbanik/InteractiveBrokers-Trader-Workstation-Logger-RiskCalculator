import tkinter as tk
from tkinter import ttk, messagebox, Toplevel
import json
import os
from threading import Thread
import time
from datetime import datetime
import sys # Import sys to check for the max float value
import math # Import math for floor and ceil
import csv # Import for CSV export functionality

# Attempt to import the ibapi library
try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.order import Order
    from ibapi.execution import ExecutionFilter, Execution
    from ibapi.commission_report import CommissionReport
except ImportError:
    # Provide a user-friendly message if ibapi is not installed
    print("Error: The 'ibapi' package is not installed.")
    print("Please install it by running: pip install ibapi")
    # Create a dummy class to avoid further errors if the GUI is started
    class EWrapper: pass
    class EClient: pass

# Attempt to import the tradingview_ta library
try:
    from tradingview_ta import TA_Handler, Interval
except ImportError:
    print("Error: The 'tradingview_ta' package is not installed.")
    print("Please install it by running: pip install tradingview_ta")
    # Create a dummy class to avoid further errors
    class TA_Handler: pass
    class Interval: pass


# --- Configuration Management ---
CONFIG_FILE = "config.json"
TRADES_FILE = "trades.json"
BALANCE_HISTORY_FILE = "accountBalances.json"

def save_config(host, port, client_id, auto_refresh_enabled, auto_refresh_seconds, auto_connect_enabled):
    """Saves connection settings to a JSON file. Returns True on success."""
    config = {
        "host": host,
        "port": port,
        "clientId": client_id,
        "auto_refresh_enabled": auto_refresh_enabled,
        "auto_refresh_seconds": auto_refresh_seconds,
        "auto_connect_on_startup": auto_connect_enabled
    }
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except IOError as e:
        print(f"Error: Could not write to config file {CONFIG_FILE}. Reason: {e}")
        return False

def load_config():
    """Loads connection settings from a JSON file."""
    if not os.path.exists(CONFIG_FILE):
        return "127.0.0.1", 7497, 1, True, 5, False
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            host = config.get("host", "127.0.0.1")
            port = config.get("port", 7497)
            client_id = config.get("clientId", 1)
            auto_refresh_enabled = config.get("auto_refresh_enabled", True)
            auto_refresh_seconds = config.get("auto_refresh_seconds", 5)
            auto_connect_enabled = config.get("auto_connect_on_startup", False)
            return host, port, client_id, auto_refresh_enabled, auto_refresh_seconds, auto_connect_enabled
    except (json.JSONDecodeError, KeyError):
        return "127.0.0.1", 7497, 1, True, 5, False

def save_trades(trades):
    """Saves the list of trades to a JSON file."""
    with open(TRADES_FILE, 'w') as f: json.dump(trades, f, indent=4)

def load_trades():
    """Loads the list of trades from a JSON file."""
    if not os.path.exists(TRADES_FILE): return []
    try:
        with open(TRADES_FILE, 'r') as f: return json.load(f)
    except json.JSONDecodeError: return []

def save_balance_history(history):
    """Saves the balance history to a JSON file."""
    with open(BALANCE_HISTORY_FILE, 'w') as f: json.dump(history, f, indent=4)

def load_balance_history():
    """Loads the balance history from a JSON file."""
    if not os.path.exists(BALANCE_HISTORY_FILE): return []
    try:
        with open(BALANCE_HISTORY_FILE, 'r') as f: return json.load(f)
    except json.JSONDecodeError: return []

# --- IBAPI Integration ---
class IBApp(EWrapper, EClient):
    """
    The main application class for interacting with the IB TWS API.
    Handles connection, requests, and data reception.
    """
    def __init__(self, app_gui):
        EClient.__init__(self, self)
        self.app_gui = app_gui
        self.nextOrderId = None
        self.next_req_id = 20000

    def get_next_req_id(self):
        """Provides a unique request ID for API calls."""
        self.next_req_id += 1
        return self.next_req_id

    def error(self, reqId, errorCode, errorString, advancedOrderReject=""):
        """Handles errors from TWS."""
        if reqId == -1 and errorCode != 2104 and errorCode != 2158 and errorCode != 2106:
             self.app_gui.update_status(f"TWS Info: {errorString}")
        elif reqId > 0 and errorCode not in [2104, 2106, 2108, 162, 321]:
            print(f"Error. Id: {reqId}, Code: {errorCode}, Msg: {errorString}")

    def connectionClosed(self):
        """Called when the connection to TWS is lost."""
        self.app_gui.update_status("Disconnected from TWS.")
        self.app_gui.reset_login_button()

    def nextValidId(self, orderId: int):
        """Receives the next valid order ID at the start of a session."""
        super().nextValidId(orderId)
        self.nextOrderId = orderId
        print(f"NextValidId received: {orderId}")
        self.reqExecutions(10001, ExecutionFilter())
        self.reqManagedAccts()

    def managedAccounts(self, accountsList: str):
        """Receives the list of managed accounts."""
        super().managedAccounts(accountsList)
        accounts = [acc for acc in accountsList.split(',') if acc]
        self.app_gui.set_managed_accounts(accounts)

    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        """Receives account summary data."""
        super().accountSummary(reqId, account, tag, value, currency)
        if tag == "NetLiquidation":
            self.app_gui.update_account_balance(account, value)
            self.app_gui.log_account_balance(account, value)
    
    def accountSummaryEnd(self, reqId: int):
        """Called when account summary is complete."""
        super().accountSummaryEnd(reqId)
        self.cancelAccountSummary(reqId)
        print(f"Account summary end for ReqId: {reqId}")

    def execDetails(self, reqId: int, contract: Contract, execution: Execution):
        """Callback receiving execution details."""
        super().execDetails(reqId, contract, execution)
        self.app_gui.update_status(f"Processing trade: {contract.symbol}...", is_temporary=True)
        trade_data = { "ExecId": execution.execId, "Time": execution.time, "Instrument": f"{contract.symbol} {contract.secType} ({contract.currency})", "Action": execution.side, "Quantity": execution.shares, "Price": execution.price, "Account": execution.acctNumber, "Commission": 0.0, "Realized P&L": 0.0 }
        self.app_gui.add_trade_to_table(trade_data)

    def commissionReport(self, commissionReport: CommissionReport):
        """Callback receiving commission and P&L details."""
        super().commissionReport(commissionReport)
        self.app_gui.update_trade_financials(commissionReport.execId, commissionReport.commission, commissionReport.realizedPNL)


# --- GUI Application ---
class TradeLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WST Trade Logger")
        self.root.geometry("1600x600")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.ib_app = None
        self.trades = load_trades()
        self.trade_exec_ids = {trade['ExecId'] for trade in self.trades if 'ExecId' in trade}
        self.exec_id_to_tree_id = {}
        self.last_status_message = ""
        self.auto_refresh_job = None
        self.managed_accounts = []
        self._load_app_config()
        
        self.sort_column = "Time"
        self.sort_reverse = True

        self._setup_styles()
        self._setup_ui()

        if self.auto_connect_on_startup:
            self.root.after(500, lambda: self.connect_to_tws(is_auto_connect=True))

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=6, relief="flat", background="#007bff", foreground="white", font=('Calibri', 10))
        style.map("TButton", background=[('active', '#0056b3'), ('disabled', '#c0c0c0')])
        style.configure("TFrame", background="#f0f0f0")
        style.configure("Treeview", rowheight=25, fieldbackground="#fdfdfd", font=('Calibri', 10))
        style.configure("Treeview.Heading", font=('Calibri', 10,'bold'), background="#e0e0e0", relief="flat")
        style.map("Treeview.Heading", relief=[('active','groove'),('pressed','sunken')])
        style.configure("Calculator.TFrame", background="#f8f9fa")
        style.configure("Result.TLabel", font=('Calibri', 10, 'bold'), background="#f8f9fa")
        style.configure("Input.TLabel", background="#f8f9fa")
        style.configure('Stepper.TButton', padding=(2, 2), font=('Calibri', 8))

    def _setup_ui(self):
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        trades_frame = ttk.Frame(main_pane, padding=10)
        main_pane.add(trades_frame, weight=3)

        top_frame = ttk.Frame(trades_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        self.login_button = ttk.Button(top_frame, text="Login to TWS", command=self.connect_to_tws)
        self.login_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.refresh_button = ttk.Button(top_frame, text="Refresh", command=self.refresh_trades, state=tk.DISABLED)
        self.refresh_button.pack(side=tk.LEFT, padx=(0, 5))

        self.bal_snapshot_button = ttk.Button(top_frame, text="Bal Snapshot", command=self.take_balance_snapshot, state=tk.DISABLED)
        self.bal_snapshot_button.pack(side=tk.LEFT, padx=(0, 5))

        self.show_bal_button = ttk.Button(top_frame, text="Show Bal", command=self.show_balance_history)
        self.show_bal_button.pack(side=tk.LEFT, padx=(0, 5))

        self.export_trades_button = ttk.Button(top_frame, text="Export Trades", command=self.export_trades_to_csv)
        self.export_trades_button.pack(side=tk.LEFT, padx=(0, 5))

        self.export_balances_button = ttk.Button(top_frame, text="Export Bal", command=self.export_balances_to_csv)
        self.export_balances_button.pack(side=tk.LEFT, padx=(0, 5))

        self.settings_button = ttk.Button(top_frame, text="Settings", command=self.open_settings)
        self.settings_button.pack(side=tk.LEFT, padx=(0, 5))

        self.columns = ("Time", "Instrument", "Action", "Quantity", "Price", "Account", "Commission", "Realized P&L")
        self.tree = ttk.Treeview(trades_frame, columns=self.columns, show="headings")
        self.tree.pack(fill=tk.BOTH, expand=True)

        headings = { "Time": {"width": 140}, "Instrument": {"width": 220}, "Action": {"width": 80, "anchor": tk.CENTER}, "Quantity": {"width": 80, "anchor": tk.E}, "Price": {"width": 100, "anchor": tk.E}, "Account": {"width": 120, "anchor": tk.CENTER}, "Commission": {"width": 100, "anchor": tk.E}, "Realized P&L": {"width": 120, "anchor": tk.E} }
        for col, props in headings.items():
            self.tree.heading(col, text=col, anchor=props.get("anchor", tk.W), command=lambda _col=col: self.sort_by_column(_col))
            self.tree.column(col, width=props["width"], anchor=props.get("anchor", tk.W))

        self._repopulate_tree()

        self._setup_calculator_ui(main_pane)

        self.status_var = tk.StringVar(value="Ready. Please login to TWS.")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _create_stepper_ui(self, parent, variable, amount):
        frame = ttk.Frame(parent, style="Calculator.TFrame")
        minus_button = ttk.Button(frame, text="-", width=2, style='Stepper.TButton', command=lambda: self._adjust_value(variable, -amount))
        minus_button.pack(side=tk.LEFT)
        plus_button = ttk.Button(frame, text="+", width=2, style='Stepper.TButton', command=lambda: self._adjust_value(variable, amount))
        plus_button.pack(side=tk.LEFT, padx=(2,0))
        return frame

    def _adjust_value(self, variable, amount):
        try:
            current_value = variable.get()
            new_value = current_value + amount
            variable.set(round(new_value, 2))
        except tk.TclError:
            variable.set(round(amount, 2))

    def _setup_calculator_ui(self, parent_pane):
        calc_outer_frame = ttk.Frame(parent_pane, style="Calculator.TFrame")
        parent_pane.add(calc_outer_frame, weight=1)
        calc_frame = ttk.LabelFrame(calc_outer_frame, text="Position Size Calculator", padding=15)
        calc_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.calc_vars = { 'Ticker': tk.StringVar(), 'AccountBalance': tk.DoubleVar(), 'RiskPrct': tk.DoubleVar(value=1.0), 'Entry': tk.DoubleVar(), 'Stop': tk.DoubleVar(), 'Target': tk.DoubleVar(), 'SelectedAccount': tk.StringVar() }
        for var in ['AccountBalance', 'RiskPrct', 'Entry', 'Stop', 'Target']: self.calc_vars[var].trace_add("write", self.update_calculations)

        # Helper function to create a row with steppers
        def create_input_row(label_text, row, variable, stepper_amount=None):
            ttk.Label(calc_frame, text=label_text, style="Input.TLabel").grid(row=row, column=0, sticky="w", pady=2)
            container = ttk.Frame(calc_frame, style="Calculator.TFrame")
            container.grid(row=row, column=1, columnspan=2, sticky="ew")
            entry = ttk.Entry(container, textvariable=variable)
            entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
            if stepper_amount:
                stepper = self._create_stepper_ui(container, variable, stepper_amount)
                stepper.pack(side=tk.LEFT, padx=(5,0))
            return entry

        # Ticker
        ttk.Label(calc_frame, text="Ticker:", style="Input.TLabel").grid(row=0, column=0, sticky="w", pady=2)
        ticker_frame = ttk.Frame(calc_frame, style="Calculator.TFrame")
        ticker_frame.grid(row=0, column=1, columnspan=2, sticky="ew")
        ttk.Entry(ticker_frame, textvariable=self.calc_vars['Ticker']).pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.fetch_price_button = ttk.Button(ticker_frame, text="Fetch Price", command=self.fetch_ticker_price_threaded)
        self.fetch_price_button.pack(side=tk.LEFT, padx=(5,0))

        # Account
        ttk.Label(calc_frame, text="Account:", style="Input.TLabel").grid(row=1, column=0, sticky="w", pady=2)
        self.account_dropdown = ttk.Combobox(calc_frame, textvariable=self.calc_vars['SelectedAccount'], state='readonly')
        self.account_dropdown.grid(row=1, column=1, columnspan=2, sticky="ew")
        self.account_dropdown.bind("<<ComboboxSelected>>", self.on_account_selected)
        
        # Account Balance
        ttk.Label(calc_frame, text="Account Balance:", style="Input.TLabel").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(calc_frame, textvariable=self.calc_vars['AccountBalance'], state='readonly').grid(row=2, column=1, columnspan=2, sticky="ew")

        # Stepper Inputs
        create_input_row("Risk (%):", 3, self.calc_vars['RiskPrct'], 0.25)
        create_input_row("Entry:", 4, self.calc_vars['Entry'], 1.0)
        create_input_row("Stop:", 5, self.calc_vars['Stop'], 1.0)
        create_input_row("Target:", 6, self.calc_vars['Target'], 1.0)

        ttk.Separator(calc_frame, orient=tk.HORIZONTAL).grid(row=7, column=0, columnspan=3, sticky="ew", pady=10)

        self.calc_result_vars = { 'AccountAtRiskPrct': tk.StringVar(value="0.00 %"), 'PositionSize': tk.StringVar(value="$0"), 'Acc1R': tk.StringVar(value="$0.00"), 'Risk-per-Share': tk.StringVar(value="$0.00"), 'Reward-Risk': tk.StringVar(value="0.00"), 'Potential': tk.StringVar(value="$0.00"), 'ShareSizeToBuy': tk.StringVar(value="0") }
        
        row_idx = 8
        for name, text in [('Acc1R', 'Account Risk (1R):'), ('Risk-per-Share', 'Risk-per-Share:'), ('ShareSizeToBuy', 'Share Size to Buy:'), ('PositionSize', 'Position Size:'), ('AccountAtRiskPrct', 'Position to Account (%):'), ('Reward-Risk', 'Reward/Risk Ratio:'), ('Potential', 'Potential Profit:')]:
            ttk.Label(calc_frame, text=text, style="Input.TLabel").grid(row=row_idx, column=0, sticky="w", pady=3)
            ttk.Label(calc_frame, textvariable=self.calc_result_vars[name], style="Result.TLabel").grid(row=row_idx, column=1, sticky="w", pady=3)
            row_idx += 1

    def update_calculations(self, *args):
        try:
            balance, risk_prct, entry, stop, target = self.calc_vars['AccountBalance'].get(), self.calc_vars['RiskPrct'].get() / 100.0, self.calc_vars['Entry'].get(), self.calc_vars['Stop'].get(), self.calc_vars['Target'].get()
            if not (0.0001 <= risk_prct <= 1): risk_prct = 0.01
            acc_1r = balance * risk_prct
            risk_per_share = abs(entry - stop) if entry > 0 and stop > 0 else 0
            share_size = math.floor(acc_1r / risk_per_share) if risk_per_share > 0 else 0
            position_size = math.ceil(entry * share_size)
            potential_per_share = abs(target - entry) if target > 0 else 0
            reward_risk_ratio = (potential_per_share / risk_per_share) if risk_per_share > 0 else 0
            potential_profit = potential_per_share * share_size
            account_at_risk_prct = (position_size / balance * 100) if balance > 0 else 0
            
            reward_risk_ratio_rounded, account_at_risk_prct_rounded = math.floor(reward_risk_ratio * 100) / 100, math.floor(account_at_risk_prct * 100) / 100

            self.calc_result_vars['Acc1R'].set(f"${acc_1r:,.2f}")
            self.calc_result_vars['Risk-per-Share'].set(f"${risk_per_share:,.2f}")
            self.calc_result_vars['ShareSizeToBuy'].set(f"{share_size:,}")
            self.calc_result_vars['PositionSize'].set(f"${position_size:,.0f}")
            self.calc_result_vars['AccountAtRiskPrct'].set(f"{account_at_risk_prct_rounded:.2f} %")
            self.calc_result_vars['Reward-Risk'].set(f"{reward_risk_ratio_rounded:.2f}")
            self.calc_result_vars['Potential'].set(f"${potential_profit:,.2f}")
        except (tk.TclError, ValueError): pass

    def fetch_ticker_price_threaded(self):
        Thread(target=self.fetch_ticker_price_from_tv, daemon=True).start()

    def fetch_ticker_price_from_tv(self):
        ticker = self.calc_vars['Ticker'].get().strip().upper()
        if not ticker:
            self.root.after(0, lambda: messagebox.showwarning("Input Required", "Please enter a ticker symbol."))
            return
        self.root.after(0, lambda: self.update_status(f"Fetching price for {ticker}...", is_temporary=True))
        exchanges, price_found = ["NASDAQ", "NYSE", "AMEX", "ARCA"], False
        for exchange in exchanges:
            try:
                handler = TA_Handler(symbol=ticker, screener="america", exchange=exchange, interval=Interval.INTERVAL_1_DAY)
                price = handler.get_analysis().indicators["close"]
                if price is not None:
                    self.root.after(0, lambda p=price: self.update_entry_price(p))
                    price_found = True
                    break
            except Exception as e:
                print(f"TradingView fetch error for {ticker} on {exchange}: {e}")
                continue
        if not price_found:
            self.root.after(0, lambda: messagebox.showerror("Fetch Error", f"Could not fetch price for {ticker} on major US exchanges.\nPlease check the symbol."))
            self.root.after(0, lambda: self.update_status("Ready.", is_temporary=False))

    def update_entry_price(self, price):
        rounded_price = round(price, 2)
        self.calc_vars['Entry'].set(rounded_price)
        self.calc_vars['Stop'].set(round(rounded_price - 1, 2))
        self.calc_vars['Target'].set(round(rounded_price + 1, 2))
        self.update_status("Price updated successfully.", is_temporary=True)

    def set_managed_accounts(self, accounts):
        self.managed_accounts = accounts
        self.populate_accounts_dropdown(accounts)
        self.take_balance_snapshot() # Auto-snapshot on connect

    def populate_accounts_dropdown(self, accounts):
        self.account_dropdown['values'] = accounts
        if accounts and not self.calc_vars['SelectedAccount'].get():
            self.calc_vars['SelectedAccount'].set(accounts[0])
            self.on_account_selected()

    def on_account_selected(self, event=None):
        account = self.calc_vars['SelectedAccount'].get()
        if account and self.ib_app and self.ib_app.isConnected():
            self.ib_app.reqAccountSummary(self.ib_app.get_next_req_id(), "All", "NetLiquidation")
    
    def update_account_balance(self, account, value):
        if account == self.calc_vars['SelectedAccount'].get():
            self.calc_vars['AccountBalance'].set(float(value))

    def log_account_balance(self, account, balance_str):
        try:
            new_balance = float(balance_str)
            history = load_balance_history()
            latest_entry = None
            for record in reversed(history):
                if record.get("Account") == account:
                    latest_entry = record
                    break
            if latest_entry is None or float(latest_entry.get("Balance", 0.0)) != new_balance:
                new_record = { "Account": account, "DateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Balance": new_balance }
                history.append(new_record)
                save_balance_history(history)
                print(f"Logged new balance for {account}: {new_balance}")
        except ValueError:
            print(f"Could not log balance for {account}, invalid value: {balance_str}")

    def take_balance_snapshot(self):
        if self.ib_app and self.ib_app.isConnected() and self.managed_accounts:
            self.update_status("Requesting balance snapshot...", is_temporary=True)
            for acc in self.managed_accounts:
                self.ib_app.reqAccountSummary(self.ib_app.get_next_req_id(), "All", "NetLiquidation")
        else:
            messagebox.showwarning("Not Connected", "Please connect to TWS to take a balance snapshot.")

    def show_balance_history(self):
        BalanceHistoryWindow(self.root)

    def export_trades_to_csv(self):
        if not self.trades:
            messagebox.showinfo("Export Info", "There are no trades to export.")
            return
        filename = "trades_export.csv"
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.trades[0].keys())
                writer.writeheader()
                writer.writerows(self.trades)
            messagebox.showinfo("Export Success", f"Trades successfully exported to {os.path.abspath(filename)}")
        except IOError as e:
            messagebox.showerror("Export Error", f"Could not write to file {filename}.\nReason: {e}")

    def export_balances_to_csv(self):
        history = load_balance_history()
        if not history:
            messagebox.showinfo("Export Info", "There is no balance history to export.")
            return
        filename = "balances_export.csv"
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=history[0].keys())
                writer.writeheader()
                writer.writerows(history)
            messagebox.showinfo("Export Success", f"Balance history successfully exported to {os.path.abspath(filename)}")
        except IOError as e:
            messagebox.showerror("Export Error", f"Could not write to file {filename}.\nReason: {e}")

    def sort_by_column(self, col):
        if self.sort_column == col: self.sort_reverse = not self.sort_reverse
        else: self.sort_column, self.sort_reverse = col, False
        def sort_key(trade):
            value = trade.get(col)
            if col in ("Quantity", "Price", "Commission", "Realized P&L"):
                try: return float(value)
                except (ValueError, TypeError): return -float('inf')
            return str(value)
        self.trades.sort(key=sort_key, reverse=self.sort_reverse)
        self._repopulate_tree()

    def _repopulate_tree(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.exec_id_to_tree_id.clear()
        for trade in self.trades:
            values = self._format_trade_for_display(trade)
            tree_id = self.tree.insert("", "end", values=values)
            if 'ExecId' in trade: self.exec_id_to_tree_id[trade['ExecId']] = tree_id

    def _load_app_config(self):
        (self.host, self.port, self.client_id, self.auto_refresh_enabled, self.auto_refresh_seconds, self.auto_connect_on_startup) = load_config()

    def _format_trade_for_display(self, trade_data):
        display_values = []
        for col in self.columns:
            value = trade_data.get(col, "")
            if col in ("Commission", "Realized P&L"):
                try: display_values.append(f"{float(value):.2f}")
                except (ValueError, TypeError): display_values.append("0.00")
            else: display_values.append(value)
        return tuple(display_values)

    def update_status(self, message, is_temporary=False):
        def _update():
            if not is_temporary: self.last_status_message = message
            self.status_var.set(message)
            if is_temporary: self.root.after(4000, lambda: self.status_var.set(self.last_status_message))
        self.root.after(0, _update)

    def reset_login_button(self):
        def _update():
            self.login_button.config(text="Login to TWS", state=tk.NORMAL)
            self.refresh_button.config(state=tk.DISABLED)
            self.bal_snapshot_button.config(state=tk.DISABLED)
            self.stop_auto_refresh()
        self.root.after(0, _update)

    def add_trade_to_table(self, trade_data):
        def _update():
            exec_id = trade_data.get("ExecId")
            if not exec_id or exec_id in self.trade_exec_ids: return
            self.trade_exec_ids.add(exec_id)
            self.trades.insert(0, trade_data)
            save_trades(self.trades)
            self.sort_by_column(self.sort_column)
        self.root.after(0, _update)

    def update_trade_financials(self, exec_id, commission, pnl):
        def _update():
            trade_to_update = next((t for t in self.trades if t.get("ExecId") == exec_id), None)
            tree_id = self.exec_id_to_tree_id.get(exec_id)
            if trade_to_update and tree_id:
                pnl_to_store = 0.0 if pnl >= sys.float_info.max else pnl
                trade_to_update["Commission"], trade_to_update["Realized P&L"] = commission, pnl_to_store
                save_trades(self.trades)
                values = self._format_trade_for_display(trade_to_update)
                self.tree.item(tree_id, values=values)
        self.root.after(0, _update)

    def connect_to_tws(self, is_auto_connect=False):
        if self.ib_app and self.ib_app.isConnected():
            if not is_auto_connect: messagebox.showinfo("Info", "Already connected to TWS.")
            return
        self._load_app_config()
        self.update_status(f"Connecting to {self.host}:{self.port} with Client ID {self.client_id}...")
        self.login_button.config(state=tk.DISABLED)
        self.ib_app = IBApp(self)
        self.ib_app.connect(self.host, self.port, clientId=self.client_id)
        Thread(target=self.ib_app.run, daemon=True).start()
        self.root.after(3000, lambda: self.check_connection_status(is_auto_connect))

    def check_connection_status(self, is_auto_connect=False):
        if self.ib_app and self.ib_app.isConnected():
            self.update_status("Successfully connected to TWS. Awaiting trades...")
            self.login_button.config(text="Connected")
            self.refresh_button.config(state=tk.NORMAL)
            self.bal_snapshot_button.config(state=tk.NORMAL)
            self.start_auto_refresh()
        else:
            if is_auto_connect: self.update_status("Auto-connect failed. Please start TWS and connect manually.")
            else: self.update_status("Connection failed. Check TWS API settings and ensure it's running.")
            self.reset_login_button()
            
    def refresh_trades(self):
        if self.ib_app and self.ib_app.isConnected():
            self.update_status("Refreshing trades...", is_temporary=True)
            self.ib_app.reqExecutions(int(time.time()), ExecutionFilter())
        elif not self.auto_connect_on_startup:
            messagebox.showwarning("Not Connected", "Please connect to TWS before refreshing.")

    def start_auto_refresh(self):
        self.stop_auto_refresh()
        if self.auto_refresh_enabled and self.ib_app and self.ib_app.isConnected():
            self.refresh_trades()
            self.auto_refresh_job = self.root.after(int(self.auto_refresh_seconds) * 1000, self.start_auto_refresh)

    def stop_auto_refresh(self):
        if self.auto_refresh_job:
            self.root.after_cancel(self.auto_refresh_job)
            self.auto_refresh_job = None

    def on_settings_changed(self):
        self._load_app_config()
        self.start_auto_refresh()

    def open_settings(self):
        SettingsWindow(self.root, self)

    def on_closing(self):
        self.stop_auto_refresh()
        if self.ib_app and self.ib_app.isConnected(): self.ib_app.disconnect()
        self.root.destroy()

class SettingsWindow(Toplevel):
    def __init__(self, parent, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.title("Settings")
        self.geometry("400x340") # Increased height
        self.transient(parent)
        self.grab_set()

        (host, port, client_id, ref_enabled, ref_seconds, auto_conn_enabled) = load_config()
        self.host_var, self.port_var, self.client_id_var = tk.StringVar(value=host), tk.StringVar(value=port), tk.StringVar(value=client_id)
        self.refresh_enabled_var, self.refresh_seconds_var, self.auto_connect_var = tk.BooleanVar(value=ref_enabled), tk.StringVar(value=ref_seconds), tk.BooleanVar(value=auto_conn_enabled)

        frame = ttk.Frame(self, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)

        conn_frame = ttk.LabelFrame(frame, text="Connection", padding=10)
        conn_frame.pack(fill=tk.X, expand=True)
        ttk.Label(conn_frame, text="TWS Host:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(conn_frame, textvariable=self.host_var).grid(row=0, column=1, sticky=tk.EW)
        ttk.Label(conn_frame, text="Port:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(conn_frame, textvariable=self.port_var).grid(row=1, column=1, sticky=tk.EW)
        ttk.Label(conn_frame, text="Client ID:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(conn_frame, textvariable=self.client_id_var).grid(row=2, column=1, sticky=tk.EW)
        conn_frame.columnconfigure(1, weight=1)

        app_frame = ttk.LabelFrame(frame, text="Application", padding=10)
        app_frame.pack(fill=tk.X, expand=True, pady=10)
        ttk.Checkbutton(app_frame, text="Enable Auto-Refresh", variable=self.refresh_enabled_var).grid(row=0, column=0, columnspan=2, sticky=tk.W)
        ttk.Label(app_frame, text="Refresh Interval (sec):").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(app_frame, textvariable=self.refresh_seconds_var, width=10).grid(row=1, column=1, sticky=tk.W)
        ttk.Checkbutton(app_frame, text="Auto-connect on startup", variable=self.auto_connect_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5,0))

        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=(10,0), side=tk.BOTTOM)
        ttk.Button(button_frame, text="OK", command=self.ok_and_close).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Apply", command=self.apply_settings).pack(side=tk.LEFT, padx=5)

    def apply_settings(self):
        try:
            port, client_id, seconds = int(self.port_var.get()), int(self.client_id_var.get()), int(self.refresh_seconds_var.get())
            if seconds < 1: raise ValueError("Interval must be positive")
            if save_config(self.host_var.get(), port, client_id, self.refresh_enabled_var.get(), seconds, self.auto_connect_var.get()):
                self.app.on_settings_changed()
                return True
            else:
                messagebox.showerror("Save Error", f"Could not save settings to {CONFIG_FILE}.\nPlease check file permissions.", parent=self)
                return False
        except ValueError:
            messagebox.showerror("Input Error", "Port, Client ID, and Interval must be valid positive numbers.", parent=self)
            return False

    def ok_and_close(self):
        if self.apply_settings(): self.destroy()

class BalanceHistoryWindow(Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Account Balance History")
        self.geometry("600x400")
        self.transient(parent)
        self.grab_set()

        self.sort_column = "DateTime"
        self.sort_reverse = True

        frame = ttk.Frame(self, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        self.columns = ("Account", "DateTime", "Balance")
        self.tree = ttk.Treeview(frame, columns=self.columns, show="headings")
        self.tree.pack(fill=tk.BOTH, expand=True)

        headings = {"Account": {"width": 120}, "DateTime": {"width": 150}, "Balance": {"width": 120, "anchor": tk.E}}
        for col, props in headings.items():
            self.tree.heading(col, text=col, anchor=props.get("anchor", tk.W), command=lambda _col=col: self.sort_by_column(_col))
            self.tree.column(col, width=props["width"], anchor=props.get("anchor", tk.W))
        
        self.history = load_balance_history()
        self.sort_by_column(self.sort_column) # Initial sort and populate

    def sort_by_column(self, col):
        if self.sort_column == col: self.sort_reverse = not self.sort_reverse
        else: self.sort_column, self.sort_reverse = col, False
        
        def sort_key(record):
            value = record.get(col)
            if col == "Balance":
                try: return float(value)
                except (ValueError, TypeError): return -float('inf')
            return str(value)

        self.history.sort(key=sort_key, reverse=self.sort_reverse)
        self._repopulate_tree()
    
    def _repopulate_tree(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for record in self.history:
            balance_formatted = f"${record.get('Balance', 0.0):,.2f}"
            values = (record.get("Account"), record.get("DateTime"), balance_formatted)
            self.tree.insert("", "end", values=values)


if __name__ == "__main__":
    missing_deps = []
    try: from ibapi.client import EClient
    except ImportError: missing_deps.append("ibapi")
    try: from tradingview_ta import TA_Handler
    except ImportError: missing_deps.append("tradingview_ta")
    if missing_deps:
         root = tk.Tk()
         root.withdraw()
         messagebox.showerror("Dependency Error", f"The following packages are not installed:\n\n{', '.join(missing_deps)}\n\nPlease install them by running:\npip install {' '.join(missing_deps)}")
    else:
        root = tk.Tk()
        app = TradeLoggerApp(root)
        root.mainloop()
