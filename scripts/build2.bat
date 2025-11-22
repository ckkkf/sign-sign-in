pyinstaller --onefile --add-data "app\config;app\config" --add-data "app\gui;app\gui" --add-data "app\mitm;app\mitm" --add-data "app\utils;app\utils" --add-data "core;core"  main.py
