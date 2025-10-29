
import tkinter as tk
from tkinter import messagebox, Toplevel, Canvas
import random
import json
from datetime import datetime
import os

# --- Config / constants ---
SAVE_FILE = "savegame.json"
BACKUP_ON_SAVE = True  # Zapisz kopię zapasową z timestampem przy każdym zapisie

TREE_TYPES = [
    {"name": "Sosna", "color": "#B2B377"},
    {"name": "Świerk", "color": "#4A6FA5"},
    {"name": "Dąb", "color": "#C68642"},
    {"name": "Brzoza", "color": "#EAEAEA"},
    {"name": "Buk", "color": "#709775"}
]

FURNITURE_TYPES = {
    "Stół": {"cost": 3, "icon": "🪑"},
    "Krzesło": {"cost": 2, "icon": "🪑"},
    "Szafa": {"cost": 5, "icon": "🗄️"},
    "Łóżko": {"cost": 4, "icon": "🛏️"}
}

LOAN_INTEREST_RATE = 0.23  # 23% jednorazowo doliczane do długu przy zaciągnięciu pożyczki
FIRE_CHANCE_PER_DAY = 0.08  # 8% szansa na pożar w end_day

# Base price table (bazowe ceny brutto)
BASE_PRICE_TABLE = {"Sosna": 20, "Świerk": 25, "Dąb": 40, "Brzoza": 15, "Buk": 35}

# How much prices can vary from base each day (e.g. 0.2 = ±20%)
MARKET_VOLATILITY = 0.20

class TycoonGame:
    def __init__(self, master):
        self.master = master
        master.title("Las Tycoon + Dom + Hazard + Podatki/Opłaty")
        # Colors / style
        self.bg_color = "#23272A"
        self.panel_color = "#1A936F"
        self.btn_color = "#4A6FA5"
        self.text_color = "#F6F5F5"
        self.warn_color = "#D7263D"

        # --- Game state ---
        self.money = 200
        self.debt = 0
        self.trees = {tree["name"]: 5 for tree in TREE_TYPES}
        # logs = drewno (pozyskiwane przy ścince)
        self.logs = {tree["name"]: 0 for tree in TREE_TYPES}
        self.selected_tree = TREE_TYPES[0]["name"]
        self.jail = False
        self.home_furniture = []
        self.furniture_counts = {name: 0 for name in FURNITURE_TYPES}
        self.furniture_buy_price = 120
        self.furniture_sell_price = 180
        self.fine_amount = 100
        self.jail_min = 5
        self.jail_max = 150
        self.day = 1
        self.days_passed = 0

        # Taxes
        self.income_tax_rate = 0.10  # 10% tax on sell earnings
        self.property_tax_per_tree = 1  # per tree per day
        self.property_tax_per_furniture = 2  # extra per furniture item per day

        # Market prices (initialized from base)
        self.market_prices = BASE_PRICE_TABLE.copy()
        # initialize daily randomization once at start
        self.randomize_market_prices(initial=True)

        # UI setup
        master.configure(bg=self.bg_color)
        self.title_label = tk.Label(master, text="Las Tycoon + Dom + Hazard + Podatki/Opłaty", font=("Helvetica", 22, "bold"), fg=self.text_color, bg=self.bg_color)
        self.title_label.pack(pady=10)

        self.select_frame = tk.Frame(master, bg=self.bg_color)
        self.select_frame.pack(pady=5)
        tk.Label(self.select_frame, text="Wybierz typ drzewa:", font=("Helvetica", 14), fg=self.text_color, bg=self.bg_color).pack(side=tk.LEFT)
        self.tree_var = tk.StringVar(value=self.selected_tree)
        for tree in TREE_TYPES:
            tk.Radiobutton(self.select_frame, text=tree["name"], variable=self.tree_var, value=tree["name"],
                           fg=self.bg_color, bg=tree["color"], font=("Helvetica", 14, "bold"),
                           selectcolor=self.panel_color, indicatoron=0, command=self.select_tree, width=10, height=2).pack(side=tk.LEFT, padx=4)

        self.stats_label = tk.Label(master, font=("Helvetica", 15), bg=self.panel_color, fg=self.text_color, justify=tk.LEFT)
        self.stats_label.pack(pady=10, fill=tk.X)

        self.cut_btn = tk.Button(master, text="Wytnij drzewo (zbierz drewno) 🌳", font=("Helvetica", 15, "bold"), bg=self.btn_color, fg=self.text_color, command=self.cut_tree, height=2, width=28)
        self.cut_btn.pack(pady=6)

        self.action_frame = tk.Frame(master, bg=self.bg_color)
        self.action_frame.pack(pady=6)
        self.sell_btn = tk.Button(self.action_frame, text="Sprzedaj drewno 💸", font=("Helvetica", 15, "bold"), bg=self.btn_color, fg=self.text_color, command=self.sell_tree, height=2, width=20)
        self.sell_btn.pack(side=tk.LEFT, padx=4)
        self.burn_btn = tk.Button(self.action_frame, text="Spal drewno w domu 🔥", font=("Helvetica", 15, "bold"), bg=self.btn_color, fg=self.text_color, command=self.burn_tree, height=2, width=26)
        self.burn_btn.pack(side=tk.LEFT, padx=4)
        self.mass_sell_btn = tk.Button(self.action_frame, text="Sprzedaj WSZYSTKIE drewno 💰", font=("Helvetica", 15, "bold"), bg=self.warn_color, fg=self.text_color, command=self.sell_all_logs, height=2, width=28)
        self.mass_sell_btn.pack(side=tk.LEFT, padx=4)

        self.jail_btn = tk.Button(master, text="Ryzykuj więzienie 🚔", font=("Helvetica", 15, "bold"), bg=self.warn_color, fg=self.text_color, command=self.go_to_jail, height=2, width=24)
        self.jail_btn.pack(pady=6)

        self.furniture_frame = tk.Frame(master, bg=self.bg_color)
        self.furniture_frame.pack(pady=6)
        self.home_btn = tk.Button(self.furniture_frame, text="Otwórz DOM 🏠", font=("Helvetica", 15, "bold"), bg=self.panel_color, fg=self.text_color, command=self.open_home, height=2, width=17)
        self.home_btn.pack(side=tk.LEFT, padx=4)
        self.craft_furniture_btn = tk.Button(self.furniture_frame, text=f"Zrób mebel", font=("Helvetica", 15, "bold"), bg=self.btn_color, fg=self.text_color, command=self.craft_furniture, height=2, width=17)
        self.craft_furniture_btn.pack(side=tk.LEFT, padx=4)

        self.hazard_frame = tk.Frame(master, bg=self.bg_color)
        self.hazard_frame.pack(pady=6)
        tk.Button(self.hazard_frame, text="Hazard 🎲", font=("Helvetica", 15, "bold"), bg="#FFD700", fg="black", command=self.open_hazard_menu, height=2, width=12).pack(side=tk.LEFT, padx=4)

        lower_frame = tk.Frame(master, bg=self.bg_color)
        lower_frame.pack(pady=6)

        self.tax_settings_btn = tk.Button(lower_frame, text="Ustawienia podatków ⚙️", font=("Helvetica", 12), bg="#888", fg="white", command=self.open_tax_settings)
        self.tax_settings_btn.pack(side=tk.LEFT, padx=4)

        # NEW: loan button
        self.loan_btn = tk.Button(lower_frame, text="Weź pożyczkę 💳", font=("Helvetica", 12), bg="#aa8844", fg="white", command=self.open_loan_window)
        self.loan_btn.pack(side=tk.LEFT, padx=4)

        # Rynek button
        self.market_btn = tk.Button(lower_frame, text="📊 Rynek", font=("Helvetica", 12), bg="#6a1b9a", fg="white", command=self.open_market_window)
        self.market_btn.pack(side=tk.LEFT, padx=4)

        self.end_day_btn = tk.Button(master, text="Koniec dnia 🌒", font=("Helvetica", 15, "bold"), bg=self.panel_color, fg=self.text_color, command=self.end_day, height=2, width=22)
        self.end_day_btn.pack(pady=10)

        # --- Przyciski zarządzania zapisem (prawy górny róg) ---
        top_corner_frame = tk.Frame(master, bg=self.bg_color)
        top_corner_frame.place(relx=1.0, rely=0.0, anchor="ne")  # prawy górny róg
        self.load_btn = tk.Button(
            top_corner_frame,
            text="📂 Wczytaj grę",
            font=("Helvetica", 11, "bold"),
            bg="#888",
            fg="white",
            command=self.manual_load_game
        )
        self.load_btn.pack(padx=6, pady=6)

        # load if exists
        self.load_game_if_exists()

        # ensure stats reflect loaded state
        self.update_stats()

        # autosave on close
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ----------------- market -----------------
    def randomize_market_prices(self, initial=False):
        """Ustaw losowe ceny rynkowe na podstawie BASE_PRICE_TABLE i MARKET_VOLATILITY.
        Jeśli initial==True -> inicjalizacja przy starcie (może być mniej zmienna)."""
        for k, base in BASE_PRICE_TABLE.items():
            # We vary by a factor in [-MARKET_VOLATILITY, +MARKET_VOLATILITY]
            # On initial load we still randomize but can be slightly milder (not necessary)
            var = random.uniform(-MARKET_VOLATILITY, MARKET_VOLATILITY)
            self.market_prices[k] = max(1, int(round(base * (1 + var))))

    def open_market_window(self):
        mw = Toplevel(self.master)
        mw.title("Rynek - ceny drewna")
        mw.geometry("360x280")
        mw.configure(bg=self.bg_color)
        tk.Label(mw, text=f"Ceny (Dzień {self.day})", font=("Helvetica", 14, "bold"), fg=self.text_color, bg=self.bg_color).pack(pady=8)
        for name in self.market_prices:
            tk.Label(mw, text=f"{name}: {self.market_prices[name]} zł (brutto)", font=("Helvetica", 13), fg=self.text_color, bg=self.bg_color).pack(anchor="w", padx=10)
        tk.Button(mw, text="Odśwież (losowe dziś)", command=lambda: (self.randomize_market_prices(), mw.destroy(), self.open_market_window()), bg=self.btn_color).pack(pady=10)

    # ----------------- state / save/load -----------------
    def get_state(self):
        return {
            "money": self.money,
            "debt": self.debt,
            "trees": self.trees,
            "logs": self.logs,
            "selected_tree": self.selected_tree,
            "jail": self.jail,
            "home_furniture": self.home_furniture,
            "furniture_counts": self.furniture_counts,
            "day": self.day,
            "days_passed": self.days_passed,
            "income_tax_rate": self.income_tax_rate,
            "property_tax_per_tree": self.property_tax_per_tree,
            "property_tax_per_furniture": self.property_tax_per_furniture,
            "market_prices": self.market_prices,
            "last_saved_at": datetime.utcnow().isoformat()
        }

    def save_game(self, filename=SAVE_FILE):
        data = self.get_state()
        try:
            if BACKUP_ON_SAVE and os.path.exists(filename):
                ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                bak = f"savegame_{ts}.json"
                with open(bak, "w", encoding="utf-8") as bf:
                    json.dump(data, bf, ensure_ascii=False, indent=2)
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Zapis", f"Zapisano grę do {filename}.")
        except Exception as e:
            messagebox.showerror("Błąd zapisu", str(e))

    def load_game_if_exists(self):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # confirm with user
            if messagebox.askyesno("Wczytaj zapis", "Znaleziono plik zapisu. Wczytać?"):
                self.load_from_dict(data)
                messagebox.showinfo("Wczytano", f"Wczytano zapis. Ostatni zapis: {data.get('last_saved_at')}")
        except FileNotFoundError:
            return
        except Exception as e:
            messagebox.showerror("Błąd odczytu zapisu", str(e))

    def manual_load_game(self):
        """Ręczne wczytanie gry z przycisku."""
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if messagebox.askyesno("Wczytaj grę", "Na pewno chcesz wczytać zapis? Niezapisane zmiany przepadną."):
                self.load_from_dict(data)
                messagebox.showinfo("Wczytano", f"Wczytano zapis z pliku {SAVE_FILE}.")
                self.update_stats()
        except FileNotFoundError:
            messagebox.showwarning("Brak zapisu", "Nie znaleziono pliku savegame.json.")
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się wczytać gry: {e}")

    def load_from_dict(self, data):
        self.money = data.get("money", self.money)
        self.debt = data.get("debt", self.debt)
        self.trees = data.get("trees", self.trees)
        self.logs = data.get("logs", self.logs)
        self.selected_tree = data.get("selected_tree", self.selected_tree)
        self.jail = data.get("jail", self.jail)
        self.home_furniture = data.get("home_furniture", self.home_furniture)
        self.furniture_counts = data.get("furniture_counts", self.furniture_counts)
        self.day = data.get("day", self.day)
        self.days_passed = data.get("days_passed", self.days_passed)
        self.income_tax_rate = data.get("income_tax_rate", self.income_tax_rate)
        self.property_tax_per_tree = data.get("property_tax_per_tree", self.property_tax_per_tree)
        self.property_tax_per_furniture = data.get("property_tax_per_furniture", self.property_tax_per_furniture)
        # load market prices if present, otherwise keep current randomized
        self.market_prices = data.get("market_prices", self.market_prices)

    # ----------------- UI / actions -----------------
    def select_tree(self):
        self.selected_tree = self.tree_var.get()
        self.update_stats()

    def update_stats(self):
        trees_state = " | ".join([f"{name}: {self.trees.get(name,0)}" for name in self.trees])
        logs_state = " | ".join([f"{name} (drewno): {self.logs.get(name,0)}" for name in self.logs])
        debt_info = f" | DŁUG: {self.debt} zł (komornik!)" if self.debt > 0 else ""
        jail_info = " | W WIĘZIENIU!" if self.jail else ""
        furniture_state = " | ".join([f"{name}: {self.furniture_counts.get(name,0)}" for name in FURNITURE_TYPES])

        # include market prices summary
        prices_state = "Ceny dziś: " + " | ".join([f"{n}: {p}zł" for n,p in self.market_prices.items()])

        self.stats_label.config(
            text=f"DZIEŃ: {self.day} (dni minęło: {self.days_passed}) | Pieniądze: {self.money} zł{debt_info}{jail_info}\nDrzewa: {trees_state}\nDrewno: {logs_state}\nWybrane drzewo: {self.selected_tree}\nMeble w domu: {furniture_state}\n{prices_state}"
        )

    def check_inspection_event(self):
        """Losowy mini-event: inspekcja leśna zabierająca 1-5 drewien z inwentarza."""
        if random.random() < 0.10:  # 10% szansy po każdej akcji
            total_logs = sum(self.logs.values())
            if total_logs <= 0:
                return  # nic nie ma do zabrania
            to_remove = random.randint(1, min(5, total_logs))
            removed = {}
            for _ in range(to_remove):
                available = [t for t, c in self.logs.items() if c > 0]
                if not available:
                    break
                t = random.choice(available)
                self.logs[t] -= 1
                removed[t] = removed.get(t, 0) + 1

            msg = "Inspekcja leśna! 🌲\n"
            msg += "Kontrola stwierdziła nieprawidłowości i skonfiskowała drewno:\n"
            msg += ", ".join([f"{t}: {c}" for t, c in removed.items()])
            messagebox.showwarning("Inspekcja!", msg)

            # Autozapis po inspekcji
            try:
                self.save_game()
            except Exception:
                pass
            self.update_stats()

    def cut_tree(self):
        # Cutting produces logs and reduces number of standing trees
        if self.trees.get(self.selected_tree,0) > 0:
            # yield per tree can vary by species; default 1 log per tree
            yield_count = 1
            # decrease standing tree
            self.trees[self.selected_tree] -= 1
            # increase logs inventory
            self.logs[self.selected_tree] = self.logs.get(self.selected_tree,0) + yield_count
            messagebox.showinfo("Wycięto!", f"Wyciąłeś: {self.selected_tree} i zdobyłeś {yield_count} drewno(drewna).")
            # check for inspection (10% chance)
            self.check_inspection_event()
            self.update_stats()
        else:
            messagebox.showwarning("Brak drzew!", f"Nie masz więcej drzew typu {self.selected_tree}.")

    def _apply_income_tax(self, gross):
        tax = int(gross * self.income_tax_rate)
        net = gross - tax
        return gross, tax, net

    def sell_tree(self):
        # Now selling sells logs (wood) from inventory, not standing trees
        if self.jail:
            messagebox.showerror("Więzienie", "Nie możesz nic zrobić będąc w więzieniu! Poczekaj na koniec dnia.")
            return
        if self.logs.get(self.selected_tree,0) < 1:
            messagebox.showwarning("Brak drewna!", "Nie masz drewna tego typu do sprzedaży.")
            return
        # risk to be caught while selling (optional)
        if random.random() < 0.12:  # slightly lower risk for selling logs
            self.go_to_jail()
            self.update_stats()
            return
        # use market price for the selected tree
        gross = self.market_prices.get(self.selected_tree, BASE_PRICE_TABLE.get(self.selected_tree,0))
        gross, tax, net = self._apply_income_tax(gross)
        # add net to money; if this operation would push money < 0, we still allow and handle debt via check_debt
        self.money += net
        self.logs[self.selected_tree] -= 1
        # check for inspection (10% chance)
        self.check_inspection_event()
        self.check_debt_post_operation()
        messagebox.showinfo("Sprzedaż", f"Sprzedałeś drewno: {self.selected_tree}.\nPrzychód brutto: {gross} zł\nPodatek: {tax} zł\nUzyskano: {net} zł")
        self.update_stats()

    def burn_tree(self):
        # Burning uses logs as fuel
        if self.jail:
            messagebox.showerror("Więzienie", "Nie możesz nic zrobić będąc w więzieniu! Poczekaj na koniec dnia.")
            return
        if self.logs.get(self.selected_tree,0) < 1:
            messagebox.showwarning("Brak drewna!", "Nie masz drewna tego typu.")
            return
        # burning gives "savings" value based on market price fraction (we'll use a smaller number)
        fuel_value_table = {"Sosna": 5, "Świerk": 7, "Dąb": 10, "Brzoza": 4, "Buk": 9}
        gross = fuel_value_table.get(self.selected_tree, 0)
        gross, tax, net = self._apply_income_tax(gross)
        self.money += net
        self.logs[self.selected_tree] -= 1
        # check for inspection (10% chance)
        self.check_inspection_event()
        self.check_debt_post_operation()
        messagebox.showinfo("Spalanie", f"Spaliłeś drewno: {self.selected_tree} w domu.\nOszczędność brutto: {gross} zł\nPodatek: {tax} zł\nUzyskano: {net} zł")
        self.update_stats()

    def sell_all_logs(self):
        # Sell all logs from inventory
        if self.jail:
            messagebox.showerror("Więzienie", "Nie możesz nic zrobić będąc w więzieniu! Poczekaj na koniec dnia.")
            return
        total_cash = 0
        total_logs = 0
        for name in list(self.logs.keys()):
            logs_to_sell = self.logs.get(name,0)
            total_cash += logs_to_sell * self.market_prices.get(name, BASE_PRICE_TABLE.get(name,0))
            total_logs += logs_to_sell
            self.logs[name] = 0
        risk = 0.06 + max(0, (total_logs-10)*0.01)  # risk adjusted
        if total_logs > 0:
            if random.random() < risk:
                self.go_to_jail()
                self.update_stats()
                return
            gross, tax, net = self._apply_income_tax(total_cash)
            self.money += net
            # check for inspection (10% chance)
            self.check_inspection_event()
            self.check_debt_post_operation()
            messagebox.showinfo("Sprzedaż masowa", f"Sprzedałeś całe drewno.\nPrzychód brutto: {gross} zł\nPodatek: {tax} zł\nUzyskano: {net} zł")
        else:
            messagebox.showwarning("Brak drewna!", "Nie masz żadnego drewna do masowej sprzedaży.")
        self.update_stats()

    def go_to_jail(self):
        self.jail = True
        jail_fine = random.choice([x for x in range(self.jail_min, self.jail_max+1, 5)])
        # fine may push into negative -> handled by check_debt_post_operation
        self.money -= jail_fine
        self.check_debt_post_operation()
        messagebox.showerror("Policja 🚨", f"Zostałeś złapany i pozbawiony wolności!\nGrzywna: {jail_fine} zł.\nNie możesz wykonywać akcji do końca dnia.")
        self.update_stats()

    # New behavior: when an operation causes money < 0, convert negative part into debt and set money to 0
    def check_debt_post_operation(self):
        if self.money < 0:
            shortage = -self.money
            self.debt += shortage
            self.money = 0
            messagebox.showwarning("Dług!", f"Twoje saldo spadło poniżej 0. Zapisano saldo jako 0 i dodano dług: {shortage} zł.")
        # keep debt displayed
        self.update_stats()

    # ----------------- furniture / home -----------------
    def craft_furniture(self):
        if self.jail:
            messagebox.showerror("Więzienie", "Nie możesz nic zrobić będąc w więzieniu.")
            return

        def make(name, cost):
            # now crafting consumes logs (wood), not standing trees
            available = sum(self.logs.values())
            if available < cost:
                messagebox.showwarning("Brak drewna!", f"Potrzebujesz {cost} drewna do wytworzenia mebla {name}.")
                return False
            used = 0
            # consume logs from inventory, arbitrary order
            for n in list(self.logs.keys()):
                while self.logs[n] > 0 and used < cost:
                    self.logs[n] -= 1
                    used += 1
            self.furniture_counts[name] = self.furniture_counts.get(name,0) + 1
            pos = self.find_free_spot()
            if pos:
                self.home_furniture.append({"type": name, "icon": FURNITURE_TYPES[name]["icon"], "x": pos[0], "y": pos[1]})
            messagebox.showinfo("Meble", f"Wytworzyłeś {name} z {cost} drewna!")
            self.update_stats()
            return True

        furniture_window = Toplevel(self.master)
        furniture_window.title("Tworzenie mebli")
        furniture_window.configure(bg=self.bg_color)
        tk.Label(furniture_window, text="Wybierz mebel do wytworzenia:", font=("Helvetica", 14), fg=self.text_color, bg=self.bg_color).pack(pady=8)
        for fname, info in FURNITURE_TYPES.items():
            btn = tk.Button(furniture_window, text=f"{fname} ({info['cost']} drewna)", font=("Helvetica", 13, "bold"),
                            bg=self.panel_color, fg=self.text_color,
                            command=lambda n=fname, c=info['cost']: (make(n,c), furniture_window.destroy()), width=22, height=2)
            btn.pack(pady=3)

    def find_free_spot(self):
        used = {(f["x"], f["y"]) for f in self.home_furniture}
        for y in range(4):
            for x in range(5):
                if (x, y) not in used:
                    return (x, y)
        return None

    def open_home(self):
        home_window = Toplevel(self.master)
        home_window.title("Twój DOM 🏠")
        home_window.configure(bg=self.bg_color)
        tk.Label(home_window, text="Meble w domu (przeciągaj by zmieniać pozycję):", font=("Helvetica", 15, "bold"), fg=self.text_color, bg=self.bg_color).pack(pady=8)
        canvas = Canvas(home_window, width=500, height=320, bg="#e0e0e0")
        canvas.pack()
        cell_size = 80

        for x in range(5):
            for y in range(4):
                canvas.create_rectangle(x*cell_size, y*cell_size, (x+1)*cell_size, (y+1)*cell_size, outline="#bbb")

        self.icon_items = []
        for idx, furn in enumerate(self.home_furniture):
            item = canvas.create_text(furn["x"]*cell_size+cell_size//2, furn["y"]*cell_size+cell_size//2,
                                     text=furn["icon"], font=("Arial", 42))
            self.icon_items.append((item, idx))

        self.dragged = None
        def start_drag(event):
            for item, idx in self.icon_items:
                coords = canvas.coords(item)
                if abs(coords[0]-event.x)<cell_size//2 and abs(coords[1]-event.y)<cell_size//2:
                    self.dragged = idx
                    break
        def drag(event):
            if self.dragged is not None:
                x = max(0, min(4, event.x//cell_size))
                y = max(0, min(3, event.y//cell_size))
                for idx, furn in enumerate(self.home_furniture):
                    if idx != self.dragged and furn['x']==x and furn['y']==y:
                        return
                self.home_furniture[self.dragged]['x'] = x
                self.home_furniture[self.dragged]['y'] = y
                for i, (item, idx) in enumerate(self.icon_items):
                    new_x = self.home_furniture[idx]['x']*cell_size+cell_size//2
                    new_y = self.home_furniture[idx]['y']*cell_size+cell_size//2
                    canvas.coords(item, new_x, new_y)
        canvas.bind("<ButtonPress-1>", start_drag)
        canvas.bind("<B1-Motion>", drag)

        # Usuwanie mebla lub sprzedaż
        control_frame = tk.Frame(home_window, bg=self.bg_color)
        control_frame.pack(pady=5)
        tk.Label(control_frame, text="Wybierz mebel:", font=("Helvetica", 12), fg=self.text_color, bg=self.bg_color).pack(side=tk.LEFT)
        select_var = tk.StringVar(value="")
        options = [f"{f['type']} ({f['x']},{f['y']})" for f in self.home_furniture]
        if options:
            select_var.set(options[0])
        select_menu = tk.OptionMenu(control_frame, select_var, *options) if options else tk.Label(control_frame, text="Brak mebli", fg=self.text_color, bg=self.bg_color)
        select_menu.pack(side=tk.LEFT)
        def remove_furniture():
            if not options:
                return
            idx = options.index(select_var.get())
            del self.home_furniture[idx]
            self.update_stats()
            home_window.destroy()
            self.open_home()
        def sell_furniture():
            if not options or select_var.get() not in options:
                messagebox.showwarning("Sprzedaż mebla", "Nie wybrano mebla.")
                return
            idx = options.index(select_var.get())
            self.money += self.furniture_sell_price
            furn_type = self.home_furniture[idx]["type"]
            self.furniture_counts[furn_type] = max(0, self.furniture_counts.get(furn_type,0)-1)
            del self.home_furniture[idx]
            self.update_stats()
            messagebox.showinfo("Sprzedaż mebla", f"Sprzedano {furn_type} za {self.furniture_sell_price} zł!")
            home_window.destroy()
            self.open_home()
        if options:
            tk.Button(control_frame, text="Usuń", command=remove_furniture, font=("Helvetica", 12), bg=self.warn_color, fg="white").pack(side=tk.LEFT, padx=4)
            tk.Button(control_frame, text=f"Sprzedaj ({self.furniture_sell_price} zł)", command=sell_furniture, font=("Helvetica", 12), bg=self.btn_color, fg="white").pack(side=tk.LEFT, padx=4)

    # ----------------- hazard (mini-games) -----------------
    def open_hazard_menu(self):
        haz_win = Toplevel(self.master)
        haz_win.title("Hazardowe Mini-Gry")
        haz_win.configure(bg=self.bg_color)
        tk.Label(haz_win, text=f"Twoje pieniądze: {self.money} zł", font=("Helvetica", 16), fg=self.text_color, bg=self.bg_color).pack(pady=10)
        tk.Button(haz_win, text="Blackjack 🃏", font=("Helvetica", 15, "bold"),
                  command=lambda: self.open_blackjack(haz_win), width=18, height=2, bg="#43a047", fg="white").pack(pady=5)
        tk.Button(haz_win, text="Poker (Draw) ♠️", font=("Helvetica", 15, "bold"),
                  command=lambda: self.open_poker(haz_win), width=18, height=2, bg="#1976d2", fg="white").pack(pady=5)
        tk.Button(haz_win, text="Bójka o drzewo 🪓", font=("Helvetica", 15, "bold"),
                  command=lambda: self.open_quick_time(haz_win), width=18, height=2, bg="#c62828", fg="white").pack(pady=5)
        tk.Button(haz_win, text="Ruletka 🎯", font=("Helvetica", 15, "bold"),
                  command=lambda: self.open_roulette(haz_win), width=18, height=2, bg="#1976d2", fg="white").pack(pady=5)
        tk.Button(haz_win, text="Jednoręki bandyta 🎰", font=("Helvetica", 15, "bold"),
                  command=lambda: self.open_slots(haz_win), width=18, height=2, bg="#FFD700", fg="black").pack(pady=5)
        tk.Button(haz_win, text="Kości 🎲", font=("Helvetica", 15, "bold"),
                  command=lambda: self.open_dice_game(haz_win), width=18, height=2, bg="#388e3c", fg="white").pack(pady=5)
        tk.Button(haz_win, text="Zgadnij liczbę🔢", font=("Helvetica", 15, "bold"),
                  command=lambda: self.open_guess_number(haz_win), width=18, height=2, bg="#e64a19", fg="white").pack(pady=5)
        tk.Button(haz_win, text="Koło fortuny 🌀", font=("Helvetica", 15, "bold"),
                  command=lambda: self.open_wheel(haz_win), width=18, height=2, bg="#5e35b1", fg="white").pack(pady=5)

    # --- BLACKJACK ---
    def open_blackjack(self, parent_win):
        bj = Toplevel(parent_win)
        bj.title("Blackjack")
        bj.geometry("400x500")
        self.bj_money = tk.IntVar(value=10)
        self.bj_cards = []
        self.bj_dealer = []
        self.bj_bet = 0
        tk.Label(bj, text="Zakład: wpisz kwotę (liczba)", font=("Helvetica", 12)).pack(pady=4)
        self.bj_label = tk.Label(bj, text="Obstaw zakład:", font=("Helvetica", 14))
        self.bj_label.pack()
        self.bj_entry = tk.Entry(bj, textvariable=self.bj_money, font=("Helvetica", 14), width=7)
        self.bj_entry.pack()
        tk.Button(bj, text="Rozpocznij", font=("Helvetica", 13, "bold"),
                  command=lambda: self.bj_start(bj), bg="#43a047", fg="white").pack(pady=6)
        self.bj_status = tk.Label(bj, text="", font=("Helvetica", 12))
        self.bj_status.pack(pady=5)
        self.bj_buttons = {}
        self.bj_result_label = tk.Label(bj, text="", font=("Helvetica", 13, "bold"))
        self.bj_result_label.pack(pady=10)

    def bj_start(self, bj_window):
        try:
            bet = int(self.bj_entry.get())
            if bet > self.money or bet <= 0:
                self.bj_result_label.config(text="Błąd: podaj poprawny zakład!")
                return
        except ValueError:
            self.bj_result_label.config(text="Błąd: podaj poprawny zakład!")
            return
        self.bj_bet = bet
        self.money -= bet
        self.update_stats()
        self.bj_cards = [random.randint(2,11), random.randint(2,11)]
        self.bj_dealer = [random.randint(2,11), random.randint(2,11)]
        self.bj_status.config(
            text=f"Twoje karty: {self.bj_cards} (suma: {sum(self.bj_cards)})\nKarty krupiera: [{self.bj_dealer[0]}, ?]"
        )
        # create buttons inside this window only
        for b in list(self.bj_buttons.values()):
            try: b.destroy()
            except: pass
        self.bj_buttons["hit"] = tk.Button(bj_window, text="Dobierz", font=("Helvetica", 13, "bold"),
                                           command=lambda: self.bj_hit(bj_window), bg="#43a047", fg="white")
        self.bj_buttons["hit"].pack(pady=3)
        self.bj_buttons["stand"] = tk.Button(bj_window, text="Stój", font=("Helvetica", 13, "bold"),
                                             command=lambda: self.bj_stand(bj_window), bg="#1976d2", fg="white")
        self.bj_buttons["stand"].pack(pady=3)

    def bj_hit(self, bj_window):
        self.bj_cards.append(random.randint(2,11))
        total = sum(self.bj_cards)
        self.bj_status.config(
            text=f"Twoje karty: {self.bj_cards} (suma: {total})\nKarty krupiera: [{self.bj_dealer[0]}, ?]"
        )
        if total > 21:
            self.bj_result_label.config(
                text=f"Przegrałeś! Przekroczyłeś 21.\nKarty krupiera: {self.bj_dealer} (suma: {sum(self.bj_dealer)})"
            )
        elif total == 21:
            self.bj_result_label.config(
                text=f"BLACKJACK! Wygrałeś podwójnie!\nKarty krupiera: {self.bj_dealer} (suma: {sum(self.bj_dealer)})"
            )

    def bj_stand(self, bj_window):
        dealer_total = sum(self.bj_dealer)
        while dealer_total < 17:
            self.bj_dealer.append(random.randint(2,11))
            dealer_total = sum(self.bj_dealer)
        player_total = sum(self.bj_cards)
        self.bj_status.config(text=f"Twoje karty: {self.bj_cards} (suma: {player_total})\nKarty krupiera: {self.bj_dealer} (suma: {dealer_total})")
        if dealer_total > 21 or player_total > dealer_total:
            self.bj_result_label.config(
                text=f"Wygrałeś!\nKarty krupiera: {self.bj_dealer} (suma: {dealer_total})"
            )
            win_sum = self.bj_bet * 1.5
            self.money += int(win_sum)
            self.update_stats()
        elif player_total < dealer_total:
            self.bj_result_label.config(
                text=f"Przegrałeś!\nKarty krupiera: {self.bj_dealer} (suma: {dealer_total})"
            )
        else:
            self.bj_result_label.config(
                text=f"Remis!\nKarty krupiera: {self.bj_dealer} (suma: {dealer_total})"
            )
            self.money += self.bj_bet
            self.update_stats()

    # --- POKER DRAW (DEMO) ---
    def open_poker(self, parent_win):
        pk = Toplevel(parent_win)
        pk.title("Poker Draw")
        pk.geometry("400x400")
        tk.Label(pk, text="Zakład: brak (demo) — tu można dodać stawkę", font=("Helvetica", 12)).pack(pady=4)
        tk.Label(pk, text="Poker 5-card draw (demo)", font=("Helvetica", 15, "bold")).pack(pady=10)
        tk.Label(pk, text="Wersja demo – pełna logika do rozbudowania!", font=("Helvetica", 12)).pack(pady=5)
        self.poker_result_label = tk.Label(pk, text="", font=("Helvetica", 14))
        self.poker_result_label.pack(pady=10)
        tk.Button(pk, text="Zagraj (losuj 5 kart)", font=("Helvetica", 14, "bold"),
                  bg="#1976d2", fg="white", command=lambda: self.poker_draw()).pack(pady=10)

    def poker_draw(self):
        deck = [f"{n}{s}" for n in list(map(str, range(2,11)))+["J","Q","K","A"] for s in ["♠", "♥", "♦", "♣"]]
        hand = random.sample(deck, 5)
        self.poker_result_label.config(text=f"Twoja ręka: {', '.join(hand)}")

    # --- QUICK TIME EVENT: BÓJKA O DRZEWO ---
    def open_quick_time(self, parent_win):
        qte = Toplevel(parent_win)
        qte.title("Bójka o drzewo")
        qte.geometry("400x320")
        tk.Label(qte, text="Zakład: brak (wygrana/strata losowa)", font=("Helvetica", 12)).pack(pady=4)
        self.qte_label = tk.Label(qte, text="Kliknij odpowiednie sekwencje na czas!", font=("Helvetica", 15, "bold"))
        self.qte_label.pack(pady=10)
        self.qte_sequence = [random.choice(["A", "S", "D", "W"]) for _ in range(5)]
        self.qte_entry = tk.Entry(qte, font=("Helvetica", 14))
        self.qte_entry.pack(pady=10)
        self.qte_result_label = tk.Label(qte, text=f"Sekwencja do wpisania: {' '.join(self.qte_sequence)}", font=("Helvetica", 13))
        self.qte_result_label.pack(pady=4)
        self.qte_btn = tk.Button(qte, text=f"Gotowe", font=("Helvetica", 14, "bold"),
                                 bg="#c62828", fg="white",
                                 command=lambda: self.qte_resolve(qte))
        self.qte_btn.pack(pady=10)

    def qte_resolve(self, qte_window):
        user_seq = self.qte_entry.get().upper().split()
        if user_seq == self.qte_sequence:
            reward = random.randint(20, 70)
            self.money += reward
            self.update_stats()
            self.qte_result_label.config(text=f"WYGRAŁEŚ bójkę! Sekwencja: {' '.join(self.qte_sequence)}\nZysk: {reward} zł.")
        else:
            loss = random.randint(10, 45)
            self.money -= loss
            self.check_debt_post_operation()
            self.update_stats()
            self.qte_result_label.config(text=f"PRZEGRAŁEŚ bójkę! Sekwencja: {' '.join(self.qte_sequence)}\nStrata: {loss} zł.")

    # --- RULETKA ---
    def open_roulette(self, parent_win):
        ru = Toplevel(parent_win)
        ru.title("Ruletka")
        ru.geometry("340x360")
        tk.Label(ru, text="Zakład: wpisz liczbę 0-36 lub kolor ('czerwony'/'czarny')", font=("Helvetica", 12)).pack(pady=4)
        tk.Label(ru, text="Ruletka – obstaw liczbę 0-36 lub kolor", font=("Helvetica", 13)).pack(pady=8)
        bet_entry = tk.Entry(ru, font=("Helvetica", 13))
        bet_entry.pack()
        tk.Label(ru, text="Stawka (zł)", font=("Helvetica", 11)).pack()
        stake_entry = tk.Entry(ru, font=("Helvetica", 13))
        stake_entry.pack()
        result_label = tk.Label(ru, text="", font=("Helvetica", 14))
        result_label.pack(pady=8)
        def play():
            try:
                stake = int(stake_entry.get())
                if stake <= 0 or stake > self.money:
                    result_label.config(text="Błąd: podaj poprawną stawkę!")
                    return
            except ValueError:
                result_label.config(text="Błąd: podaj poprawną stawkę!")
                return
            bet = bet_entry.get().strip().lower()
            result = random.randint(0,36)
            color = "czerwony" if result in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "czarny"
            win = 0
            if bet == str(result):
                win = stake*35
            elif bet == color:
                win = stake*2
            self.money += win-stake
            self.check_debt_post_operation()
            self.update_stats()
            result_label.config(text=f"Wypadło: {result} ({color})\nTwój zakład: {bet}\nWygrałeś: {win} zł" if win else f"Wypadło: {result} ({color})\nTwój zakład: {bet}\nPrzegrałeś {stake} zł.")
        tk.Button(ru, text="Graj", command=play, font=("Helvetica", 13), bg="#1976d2", fg="white").pack(pady=8)

    # --- SLOTS (Jednoręki bandyta) ---
    def open_slots(self, parent_win):
        sl = Toplevel(parent_win)
        sl.title("Jednoręki bandyta")
        sl.geometry("320x260")
        tk.Label(sl, text="Zakład: wpisz stawkę (liczba)", font=("Helvetica", 12)).pack(pady=4)
        tk.Label(sl, text="Slot Machine – obstaw stawkę", font=("Helvetica", 13)).pack(pady=8)
        stake_entry = tk.Entry(sl, font=("Helvetica", 13))
        stake_entry.pack()
        result_label = tk.Label(sl, text="", font=("Helvetica", 17))
        result_label.pack(pady=8)
        def play():
            try:
                stake = int(stake_entry.get())
                if stake <= 0 or stake > self.money:
                    result_label.config(text="Błąd: podaj poprawną stawkę!")
                    return
            except ValueError:
                result_label.config(text="Błąd: podaj poprawną stawkę!")
                return
            symbols = ["🍒","💎","🔔","🍋","🍀","7️⃣"]
            roll = [random.choice(symbols) for _ in range(3)]
            win = 0
            if roll[0]==roll[1]==roll[2]:
                win = stake*10
            elif roll.count("7️⃣")==2:
                win = stake*5
            elif "💎" in roll:
                win = stake*2
            self.money += win-stake
            self.check_debt_post_operation()
            self.update_stats()
            result_label.config(text=f"Symbole: {' '.join(roll)}\nWygrałeś {win} zł" if win else f"Symbole: {' '.join(roll)}\nPrzegrałeś {stake} zł.")
        tk.Button(sl, text="Graj", command=play, font=("Helvetica", 13), bg="#FFD700", fg="black").pack(pady=8)

    # --- KOŚCI ---
    def open_dice_game(self, parent_win):
        dice = Toplevel(parent_win)
        dice.title("Kości")
        dice.geometry("320x220")
        tk.Label(dice, text="Zakład: wpisz stawkę oraz zgadnij sumę dwóch kości (2-12)", font=("Helvetica", 12)).pack(pady=4)
        tk.Label(dice, text="Kości – obstaw sumę dwóch kości (2-12)", font=("Helvetica", 13)).pack(pady=8)
        stake_entry = tk.Entry(dice, font=("Helvetica", 13))
        stake_entry.pack()
        sum_entry = tk.Entry(dice, font=("Helvetica", 13))
        sum_entry.pack()
        result_label = tk.Label(dice, text="", font=("Helvetica", 14))
        result_label.pack(pady=8)
        def play():
            try:
                stake = int(stake_entry.get())
                guess = int(sum_entry.get())
                if stake <= 0 or stake > self.money or guess<2 or guess>12:
                    result_label.config(text="Błąd: podaj poprawne dane!")
                    return
            except ValueError:
                result_label.config(text="Błąd: podaj poprawne dane!")
                return
            d1, d2 = random.randint(1,6), random.randint(1,6)
            win = 0
            if guess == d1+d2:
                win = stake*10
            self.money += win-stake
            self.check_debt_post_operation()
            self.update_stats()
            result_label.config(text=f"Wypadło: {d1}+{d2}={d1+d2}\nTwój zakład: {guess}\nWygrałeś {win} zł" if win else f"Wypadło: {d1}+{d2}={d1+d2}\nTwój zakład: {guess}\nPrzegrałeś {stake} zł.")
        tk.Button(dice, text="Graj", command=play, font=("Helvetica", 13), bg="#388e3c", fg="white").pack(pady=8)

    # --- ZGADNIJ LICZBĘ (zmiany: 1-100, 5 prób, wskazówki większa/mniejsza) ---
    def open_guess_number(self, parent_win):
        gn = Toplevel(parent_win)
        gn.title("Zgadnij liczbę")
        gn.geometry("360x220")
        tk.Label(gn, text="Zakład: wpisz stawkę (liczba). Zgadnij liczbę 1-100. Masz 5 prób.", font=("Helvetica", 12)).pack(pady=6)
        stake_label = tk.Label(gn, text="Stawka (zł):", font=("Helvetica", 11))
        stake_label.pack()
        stake_entry = tk.Entry(gn, font=("Helvetica", 13))
        stake_entry.pack()
        tk.Label(gn, text="Twoje zgadnięcie (1-100):", font=("Helvetica", 11)).pack(pady=4)
        guess_entry = tk.Entry(gn, font=("Helvetica", 13))
        guess_entry.pack()
        result_label = tk.Label(gn, text="", font=("Helvetica", 14))
        result_label.pack(pady=8)

        secret = random.randint(1,100)
        attempts = {"count": 0}
        max_attempts = 5

        def play():
            try:
                stake = int(stake_entry.get())
                guess = int(guess_entry.get())
                if stake <= 0 or stake > self.money or guess < 1 or guess > 100:
                    result_label.config(text="Błąd: podaj poprawne dane!")
                    return
            except ValueError:
                result_label.config(text="Błąd: podaj poprawne dane!")
                return

            attempts["count"] += 1
            if guess == secret:
                win = stake * 10
                self.money += win - stake  # reward as before (net)
                self.check_debt_post_operation()
                self.update_stats()
                result_label.config(text=f"WYGRAŁEŚ! Liczba to {secret}. Wygrałeś {win} zł.")
                return
            else:
                # provide hint
                hint = "Większa" if guess < secret else "Mniejsza"
                if attempts["count"] < max_attempts:
                    result_label.config(text=f"Źle! {hint}. Próba {attempts['count']}/{max_attempts}.")
                    return
                else:
                    # last attempt failed -> subtract stake
                    self.money -= stake
                    self.check_debt_post_operation()
                    self.update_stats()
                    result_label.config(text=f"PRZEGRAŁEŚ! Liczba to {secret}. Strata: {stake} zł.")
                    return

        tk.Button(gn, text="Zgadnij", command=play, font=("Helvetica", 13), bg="#e64a19", fg="white").pack(pady=8)

    def open_wheel(self, parent_win):
        wf = Toplevel(parent_win)
        wf.title("Koło fortuny")
        wf.geometry("320x200")
        tk.Label(wf, text="Zakład: wpisz stawkę (liczba)", font=("Helvetica", 12)).pack(pady=4)
        tk.Label(wf, text="Koło fortuny – obstaw stawkę", font=("Helvetica", 13)).pack(pady=8)
        stake_entry = tk.Entry(wf, font=("Helvetica", 13))
        stake_entry.pack()
        result_label = tk.Label(wf, text="", font=("Helvetica", 14))
        result_label.pack(pady=8)
        def play():
            try:
                stake = int(stake_entry.get())
                if stake <= 0 or stake > self.money:
                    result_label.config(text="Błąd: podaj poprawną stawkę!")
                    return
            except ValueError:
                result_label.config(text="Błąd: podaj poprawną stawkę!")
                return
            prizes = [0, stake*2, stake*5, stake*10, stake*20]
            win = random.choice(prizes)
            self.money += win-stake
            self.check_debt_post_operation()
            self.update_stats()
            result_label.config(text=f"Koło zatrzymało się na {win} zł!\nWygrałeś {win} zł." if win else f"Koło zatrzymało się na 0 zł!\nPrzegrałeś {stake} zł.")
        tk.Button(wf, text="Zakręć", command=play, font=("Helvetica", 13), bg="#5e35b1", fg="white").pack(pady=8)

    # ----------------- end of day, taxes, autosave, fire chance -----------------
    def apply_property_tax(self):
        trees_count = sum(self.trees.values())
        tax_trees = self.property_tax_per_tree * trees_count
        tax_furn = self.property_tax_per_furniture * sum(self.furniture_counts.values())
        total_tax = tax_trees + tax_furn
        if total_tax <= 0:
            return []
        charges = []
        if self.money >= total_tax:
            self.money -= total_tax
            charges.append(f"Podatek od posiadanych drzew/mebli: -{total_tax} zł")
        else:
            # if can't pay, set money to zero and mark debt
            charges.append(f"Nie stać Cię na podatek ({total_tax} zł). Konto idzie na 0, reszta traktowana jako dług.")
            self.debt += total_tax - max(0, self.money)
            self.money = 0
        return charges

    def end_day(self):
        self.day += 1
        self.days_passed += 1
        charges = []
        # Opłaty za prąd
        prad = random.randint(10, 40)
        self.money -= prad
        charges.append(f"Prąd: -{prad} zł")
        # Podatek od nieruchomości zależny od mebli i drzew
        tax_charges = self.apply_property_tax()
        charges.extend(tax_charges)
        if self.jail:
            self.jail = False
            charges.append("Wyszedłeś z więzienia")
        # drzewka rosną (prosty mechanizm: dostajesz 1 nowego drzewa każdego dnia każdego typu)
        for name in self.trees:
            self.trees[name] += 1

        # ---- NEW: chance of random fire destroying some trees ----
        total_trees = sum(self.trees.values())
        if total_trees > 0 and random.random() < FIRE_CHANCE_PER_DAY:
            # lose between 1 and up to 25% of total trees
            max_loss = max(1, total_trees // 4)
            total_lost = random.randint(1, max_loss)
            lost_details = {}
            for _ in range(total_lost):
                # choose a random species that still has trees
                available_species = [s for s in self.trees if self.trees[s] > 0]
                if not available_species:
                    break
                s = random.choice(available_species)
                self.trees[s] -= 1
                lost_details[s] = lost_details.get(s, 0) + 1
            # message about fire
            parts = [f"{k}: {v}" for k, v in lost_details.items()]
            charges.append(f"POŻAR! Straciłeś {sum(lost_details.values())} drzew: " + ", ".join(parts))

        # komornik (prosty mechanizm jeśli masz dług)
        if self.debt > 0:
            taken = int(self.debt * 0.1)
            if self.money >= taken:
                self.money -= taken
                self.debt -= taken
                charges.append(f"Komornik pobrał: -{taken} zł")
            else:
                charges.append(f"Komornik próbował pobrać {taken} zł, ale brak środków.")
                # if cannot pay, debt increases by attempted collection (keeps compounding)
                self.debt += taken

        # Randomize market prices for the new day
        self.randomize_market_prices()

        # autosave after day
        try:
            self.save_game()
            charges.append("Gra została zapisana.")
        except Exception:
            pass

        # After all per-day operations, ensure negative money is converted into debt
        self.check_debt_post_operation()
        self.update_stats()
        messagebox.showinfo("Podsumowanie dnia", " | ".join(charges) if charges else "Brak opłat dzisiaj.")

    # ----------------- tax settings UI -----------------
    def open_tax_settings(self):
        t = Toplevel(self.master)
        t.title("Ustawienia podatków")
        t.configure(bg=self.bg_color)
        tk.Label(t, text="Ustawienia podatków", font=("Helvetica", 14, "bold"), fg=self.text_color, bg=self.bg_color).pack(pady=8)
        # income tax
        frame1 = tk.Frame(t, bg=self.bg_color)
        frame1.pack(pady=4)
        tk.Label(frame1, text="Podatek dochodowy przy sprzedaży (%)", fg=self.text_color, bg=self.bg_color).pack(side=tk.LEFT, padx=4)
        income_var = tk.DoubleVar(value=self.income_tax_rate*100)
        tk.Entry(frame1, textvariable=income_var, width=6).pack(side=tk.LEFT)
        # property tax per tree
        frame2 = tk.Frame(t, bg=self.bg_color)
        frame2.pack(pady=4)
        tk.Label(frame2, text="Podatek od drzewa (zł/dzień)", fg=self.text_color, bg=self.bg_color).pack(side=tk.LEFT, padx=4)
        prop_tree_var = tk.IntVar(value=self.property_tax_per_tree)
        tk.Entry(frame2, textvariable=prop_tree_var, width=6).pack(side=tk.LEFT)
        # property tax per furniture
        frame3 = tk.Frame(t, bg=self.bg_color)
        frame3.pack(pady=4)
        tk.Label(frame3, text="Podatek od mebla (zł/dzień)", fg=self.text_color, bg=self.bg_color).pack(side=tk.LEFT, padx=4)
        prop_furn_var = tk.IntVar(value=self.property_tax_per_furniture)
        tk.Entry(frame3, textvariable=prop_furn_var, width=6).pack(side=tk.LEFT)
        def apply_settings():
            try:
                it = float(income_var.get())
                pt = int(prop_tree_var.get())
                pf = int(prop_furn_var.get())
                if it < 0 or it > 100 or pt < 0 or pf < 0:
                    raise ValueError
                self.income_tax_rate = it/100.0
                self.property_tax_per_tree = pt
                self.property_tax_per_furniture = pf
                messagebox.showinfo("Ustawienia", "Zastosowano ustawienia podatków.")
                t.destroy()
                self.update_stats()
            except Exception:
                messagebox.showerror("Błąd", "Wprowadź poprawne wartości.")
        tk.Button(t, text="Zapisz", command=apply_settings, bg=self.btn_color).pack(pady=8)

    # ----------------- loan UI & handling -----------------
    def open_loan_window(self):
        lw = Toplevel(self.master)
        lw.title("Weź pożyczkę")
        lw.configure(bg=self.bg_color)
        tk.Label(lw, text="Podaj kwotę pożyczki (zł):", font=("Helvetica", 13), fg=self.text_color, bg=self.bg_color).pack(pady=8)
        amt_var = tk.StringVar(value="100")
        entry = tk.Entry(lw, textvariable=amt_var, font=("Helvetica", 13))
        entry.pack(pady=4)
        info = tk.Label(lw, text=f"Odsetki: {int(LOAN_INTEREST_RATE*100)}% od pożyczonej kwoty (doliczane do długu)", fg=self.text_color, bg=self.bg_color)
        info.pack(pady=4)
        def take():
            try:
                amt = int(amt_var.get())
                if amt <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Błąd", "Podaj poprawną kwotę (liczba całkowita).")
                return
            # grant money and add interest to debt
            self.money += amt
            added_debt = int(round(amt * (1.0 + LOAN_INTEREST_RATE)))
            # You requested that interest is 23% of the borrowed amount — here we add principal+interest to debt
            self.debt += added_debt
            messagebox.showinfo("Pożyczka", f"Pożyczono {amt} zł.\nDo długu dopisano kwotę: {added_debt} zł (principal + {int(LOAN_INTEREST_RATE*100)}% odsetek).")
            self.update_stats()
            lw.destroy()
        tk.Button(lw, text="Weź pożyczkę", command=take, bg="#aa8844").pack(pady=8)

    # ----------------- save on close -----------------
    def on_closing(self):
        if messagebox.askyesno("Zapis", "Chcesz zapisać przed wyjściem?"):
            try:
                self.save_game()
            except Exception:
                pass
        self.master.destroy()

# ----------------- run -----------------
if __name__ == "__main__":
    root = tk.Tk()
    game = TycoonGame(root)
    root.mainloop()
