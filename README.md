# Trader Logger & Risk Calculator for InteractiveBrokers Trader Workstation (WST)

A desktop application built with Python and Tkinter that connects to the Interactive Brokers Trader Workstation (TWS) API to log trades, track account balances, and assist with position sizing.

## Core Features

-   **Automated Trade Logging**: Connects to TWS and automatically fetches and displays trade execution details in real-time.
-   **Account Balance Tracking**: Retrieves and displays the Net Liquidation value for managed accounts and logs a history of balance snapshots.
-   **Position Size Calculator**: An integrated tool to calculate share size based on account balance, risk percentage, entry, stop, and target prices.
-   **Live Price Data**: Fetches the last price for a given ticker from TradingView to populate the calculator's entry price.
-   **Data Export**: Exports trade logs and account balance history to CSV files for external analysis.
-   **Persistent Storage**: Saves trades, balance history, and application settings locally in JSON files.
-   **Configurable**: Settings for TWS connection, auto-refresh intervals, and auto-connect on startup can be modified through the UI.

!(TL.jpg)

## Dependencies and Setup

### 1. Python Libraries

The application requires the following Python packages. Install them using pip:

```bash
pip install ibapi tradingview_ta
```

### 2. External Applications

-   **Interactive Brokers Trader Workstation (TWS)**: You must have a running instance of TWS or IB Gateway to which the application can connect. The logger does not depend on any other external executables. The `faster-whisper-xxl.exe` file mentioned is not a dependency for this application.

If an application were to require an external executable from a source like GitHub, the process would be:
1.  Navigate to the project's GitHub repository.
2.  Go to the "Releases" section on the right-hand side.
3.  Find the desired version and download the executable from the "Assets" list.
4.  Place the executable in the same directory as the script or in a directory included in your system's PATH.

## Configuration

### Interactive Brokers TWS API

The TWS API must be configured to accept connections. This application only requires read-only access.

1.  In TWS, navigate to **File -> Global Configuration**.
2.  In the left pane, select **API -> Settings**.
3.  Check the box for **Enable ActiveX and Socket Clients**.
4.  For security, check the box for **Read-Only API**. This prevents the application from modifying orders or account data.
5.  Ensure the **Socket port** number matches the port in the Trade Logger's settings (default is `7497`).
6.  Click **Apply** and **OK**.

!(IBTWS.jpg)

### Application Settings

Within the Trade Logger, click the "Settings" button to configure:
-   TWS Host IP
-   Socket Port
-   Client ID
-   Auto-refresh settings
-   Auto-connect on startup

!(SETTINGS.jpg)

## Running the Application

1.  Ensure TWS is running and configured correctly.
2.  Run the script from your terminal:
    ```bash
    python tradelogger.py
    ```
3.  Alternatively, run the `build.bat` script to create a standalone Windows executable (`TradeLogger.exe`) in the `dist` folder. This requires `pyinstaller` to be installed (`pip install pyinstaller`).

