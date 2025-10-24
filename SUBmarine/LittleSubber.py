import sys
import json
from datetime import datetime
import os
import webbrowser
import colorsys
import requests
from bs4 import BeautifulSoup
import io
from urllib.parse import urlparse

# Optional favicon import for dynamic tracking
HAS_FAVICON = True
try:
    import favicon
except ImportError:
    HAS_FAVICON = False

# Ensure the system tkinter (TK) library is available. customtkinter depends on
# the stdlib tkinter which is often provided by a separate system package
# (for example `python3-tk` on Debian/Ubuntu). If it's missing, we fall back to
# a basic CLI so the script doesn't crash and basic subscription management
# still works.
HAS_TK = True
try:
    import tkinter  # noqa: F401 - runtime check only
except Exception:
    HAS_TK = False
    print("Warning: the 'tkinter' module is not available in this Python environment.")
    print("customtkinter (the GUI) won't be available. Falling back to CLI mode.")
    print("To enable the GUI, install your system's Tk package (e.g. python3-tk).")

if HAS_TK:
    try:
        import customtkinter as ctk
        from PIL import Image
        import tkinter.messagebox as messagebox
    except Exception:
        # If customtkinter or other GUI libs are missing, fall back to CLI.
        HAS_TK = False
        print("Warning: required GUI Python packages are not available in the environment.")
        print("Falling back to CLI mode. You can install packages with:")
        print("  python -m pip install --user customtkinter CTkMessagebox Pillow")

    # If HAS_TK remains True, the GUI class will be defined below.

if HAS_TK:
    class SubscriptionTracker(ctk.CTk):
        def __init__(self):
            # Load settings first
            self.settings = self.load_settings()
            
            # Configure appearance
            self.appearance_mode = self.settings.get("appearance_mode", "dark")
            ctk.set_appearance_mode(self.appearance_mode)
            
            # Initialize window
            super().__init__()
            self.title("SUBmarine")
            self.geometry("800x600")
            
            # Apply scaling
            self.apply_scaling(self.settings.get("scaling_factor", 1.0))
            
            # Initialize data storage
            self.subscriptions = []
            self.load_subscriptions()
            
            # Create main layout
            self.create_widgets()
            
        def create_widgets(self):
            # Sidebar
            self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
            self.sidebar.pack(side="left", fill="y", padx=0, pady=0)
            
            # Logo/Title
            self.logo_label = ctk.CTkLabel(self.sidebar, text="SUBmarine", 
                                          font=ctk.CTkFont(size=24, weight="bold"))
            self.logo_label.pack(pady=20)
            
            # Add subscription button
            self.add_button = ctk.CTkButton(self.sidebar, text="Add Subscription",
                                           command=self.show_add_dialog)
            self.add_button.pack(pady=10, padx=20)
            
            # Settings button
            self.settings_button = ctk.CTkButton(self.sidebar, text="Settings",
                                               command=self.show_settings_dialog)
            self.settings_button.pack(pady=10, padx=20)
            
            # Stats Frame
            self.stats_frame = ctk.CTkFrame(self.sidebar)
            self.stats_frame.pack(pady=20, padx=20, fill="x")
            
            self.monthly_total = ctk.CTkLabel(self.stats_frame, text="Monthly Total: $0.00")
            self.monthly_total.pack(pady=5)
            
            self.yearly_total = ctk.CTkLabel(self.stats_frame, text="Yearly Total: $0.00")
            self.yearly_total.pack(pady=5)
            
            # Main content area
            self.main_frame = ctk.CTkScrollableFrame(self)
            self.main_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)
            
            self.refresh_subscription_list()
            
            # Apply initial colors if they exist
            self.apply_color_theme(self.settings.get("hue", 200))
            
        def show_add_dialog(self):
            dialog = ctk.CTkToplevel(self)
            dialog.title("Add Subscription")
            dialog.geometry("400x400")
            dialog.resizable(False, False)
            dialog.transient(self)  # Make dialog modal
            
            # Wait for the dialog to be visible before setting grab
            self.wait_visibility(dialog)
            dialog.grab_set()  # Make dialog modal
            
            # Create a main frame for proper padding
            main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            main_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
            # Form fields
            ctk.CTkLabel(main_frame, text="Service Name:").pack(pady=(0, 5))
            name_entry = ctk.CTkEntry(main_frame)
            name_entry.pack(fill="x")
            
            ctk.CTkLabel(main_frame, text="Price:").pack(pady=(15, 5))
            price_entry = ctk.CTkEntry(main_frame)
            price_entry.pack(fill="x")
            
            ctk.CTkLabel(main_frame, text="Billing Cycle:").pack(pady=(15, 5))
            cycle_var = ctk.StringVar(value="Monthly")
            cycle_menu = ctk.CTkOptionMenu(main_frame, values=["Monthly", "Yearly"],
                                         variable=cycle_var)
            cycle_menu.pack(fill="x")
            
            ctk.CTkLabel(main_frame, text="Website URL:").pack(pady=(15, 5))
            website_entry = ctk.CTkEntry(main_frame)
            website_entry.pack(fill="x")
            
            # Dynamic tracking option
            dynamic_var = ctk.BooleanVar(value=True)
            dynamic_checkbox = ctk.CTkCheckBox(main_frame, text="Dynamic Tracking (auto-fetch website info and icon)",
                                             variable=dynamic_var)
            dynamic_checkbox.pack(pady=(15, 5))
            
            def save():
                name = name_entry.get().strip()
                if not name:
                    messagebox.showerror("Error", "Please enter a service name")
                    return

                try:
                    price = float(price_entry.get())
                    if price <= 0:
                        raise ValueError("Price must be positive")
                except ValueError:
                    messagebox.showerror("Error", "Please enter a valid positive price")
                    return
                
                website = website_entry.get().strip()
                if website and not website.startswith(('http://', 'https://')):
                    website = 'https://' + website
                    
                # Dynamic tracking
                icon_data = None
                if dynamic_var.get() and website:
                    dialog.configure(cursor="wait")
                    title, icon_data = self.fetch_website_info(website)
                    dialog.configure(cursor="")
                
                sub = {
                    "name": name,
                    "price": price,
                    "cycle": cycle_var.get(),
                    "website": website,
                    "date_added": datetime.now().strftime("%Y-%m-%d")
                }
                
                if icon_data:
                    sub["icon"] = icon_data.hex()  # Store binary data as hex string
                    
                self.subscriptions.append(sub)
                self.save_subscriptions()
                self.refresh_subscription_list()
                dialog.destroy()
            
            # Fixed-height footer frame to ensure consistent button layout
            footer_frame = ctk.CTkFrame(main_frame, fg_color="transparent", height=80)
            footer_frame.pack(fill="x", pady=(20, 0), side="bottom")
            footer_frame.pack_propagate(False)  # Prevent the frame from shrinking
            
            # Button frame inside footer with grid layout
            button_frame = ctk.CTkFrame(footer_frame, fg_color="transparent")
            button_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0)
            
            # Use grid layout for buttons so they never collapse
            button_frame.grid_columnconfigure(0, weight=1)
            button_frame.grid_columnconfigure(1, weight=1)

            btn_font = ctk.CTkFont(size=14, weight="bold")
            cancel_btn = ctk.CTkButton(
                button_frame,
                text="Cancel",
                command=dialog.destroy,
                width=120,
                height=40,
                corner_radius=8,
                font=btn_font
            )
            save_btn = ctk.CTkButton(
                button_frame,
                text="Save",
                command=save,
                width=120,
                height=40,
                corner_radius=8,
                font=btn_font,
                fg_color=self.get_color(self.settings.get("hue", 200))
            )

            # Place buttons in the grid
            cancel_btn.grid(row=0, column=0, sticky="ew", padx=8)
            save_btn.grid(row=0, column=1, sticky="ew", padx=8)
            
            # Set focus to name entry
            name_entry.focus_set()
            
            # Bind Enter key to save
            dialog.bind("<Return>", lambda e: save())
            dialog.bind("<Escape>", lambda e: dialog.destroy())
            
        def show_settings_dialog(self):
            dialog = ctk.CTkToplevel(self)
            dialog.title("Settings")
            dialog.geometry("500x700")
            dialog.resizable(False, False)
            dialog.transient(self)

            # Wait for the dialog to be visible before setting grab
            self.wait_visibility(dialog)
            dialog.grab_set()

            # Main frame for proper padding
            main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            main_frame.pack(fill="both", expand=True, padx=20, pady=20)

            # Tabview for settings
            tabview = ctk.CTkTabview(main_frame, width=450, height=600)
            tabview.pack(fill="both", expand=True)

            # Display Tab
            display_tab = tabview.add("Display")

            # Display Scaling Section
            scaling_frame = ctk.CTkFrame(display_tab)
            scaling_frame.pack(fill="x", pady=(10, 20))

            ctk.CTkLabel(scaling_frame, text="Display Scaling",
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

            # Create more granular scaling options from 75% to 300% in quarter steps
            scale_values = []
            for i in range(3, 13):  # 0.75 (3/4) to 3.00 (12/4)
                scale_values.append(f"{i/4:.2f}")
            scale_options = {scale: f"{int(float(scale)*100)}%" for scale in scale_values}

            def on_scale_change(choice):
                factor = float(choice.split("%")[0]) / 100
                self.settings["scaling_factor"] = factor
                self.save_settings()
                self.apply_scaling(factor)

            scale_menu = ctk.CTkOptionMenu(
                scaling_frame,
                values=list(scale_options.values()),
                command=on_scale_change
            )
            current_scale = f"{int(float(self.settings.get('scaling_factor', 1.0)) * 100)}%"
            scale_menu.set(current_scale)
            scale_menu.pack(pady=5)

            # Appearance Section
            appearance_frame = ctk.CTkFrame(display_tab)
            appearance_frame.pack(fill="x", pady=(0, 20))

            ctk.CTkLabel(appearance_frame, text="Appearance",
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

            # Mode selection (Light/Dark)
            ctk.CTkLabel(appearance_frame, text="Theme Mode:").pack(pady=(5, 0))
            mode_var = ctk.StringVar(value=self.settings.get("appearance_mode", "dark"))

            def on_mode_change(choice):
                self.appearance_mode = choice.lower()
                self.settings["appearance_mode"] = self.appearance_mode
                self.save_settings()
                ctk.set_appearance_mode(self.appearance_mode)

            mode_menu = ctk.CTkOptionMenu(
                appearance_frame,
                values=["Light", "Dark"],
                command=on_mode_change
            )
            mode_menu.set(self.appearance_mode.capitalize())
            mode_menu.pack(pady=5)

            # Color customization with rainbow slider
            ctk.CTkLabel(appearance_frame, text="Color Theme:",
                        font=ctk.CTkFont(weight="bold")).pack(pady=(15, 5))

            # Create a frame for the color preview
            preview_frame = ctk.CTkFrame(appearance_frame, height=30)
            preview_frame.pack(fill="x", pady=(0, 10), padx=20)

            # Rainbow slider
            hue_slider = ctk.CTkSlider(
                appearance_frame,
                from_=0,
                to=360,
                number_of_steps=360,
                command=self.apply_color_theme,
                progress_color=self.get_color(self.settings.get("hue", 200))
            )
            hue_slider.pack(fill="x", pady=5, padx=20)

            # Set initial hue value
            hue_slider.set(self.settings.get("hue", 200))

            # Notifications Tab
            notifications_tab = tabview.add("Notifications")

            # Notifications enabled switch
            enabled_frame = ctk.CTkFrame(notifications_tab)
            enabled_frame.pack(fill="x", pady=(10, 20))

            ctk.CTkLabel(enabled_frame, text="Notifications Enabled",
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

            enabled_switch = ctk.CTkSwitch(
                enabled_frame,
                text="",
                command=lambda: self.toggle_notification_enabled(enabled_switch)
            )
            enabled_switch.pack(pady=5)
            enabled_switch.select() if self.settings.get("notifications_enabled", False) else enabled_switch.deselect()

            # When to notify
            when_frame = ctk.CTkFrame(notifications_tab)
            when_frame.pack(fill="x", pady=(0, 20))

            ctk.CTkLabel(when_frame, text="When to Notify",
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

            when_options = ["1 day", "3 days", "1 week", "2 weeks"]
            when_menu = ctk.CTkOptionMenu(
                when_frame,
                values=when_options,
                command=lambda choice: self.update_setting("notification_when", choice)
            )
            when_menu.set(self.settings.get("notification_when", "3 days"))
            when_menu.pack(pady=5)

            # Push notifications
            push_frame = ctk.CTkFrame(notifications_tab)
            push_frame.pack(fill="x", pady=(0, 20))

            ctk.CTkLabel(push_frame, text="Push Notifications",
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

            push_switch = ctk.CTkSwitch(
                push_frame,
                text="",
                command=lambda: self.toggle_notification_push(push_switch)
            )
            push_switch.pack(pady=5)
            push_switch.select() if self.settings.get("notification_push", False) else push_switch.deselect()

            # Custom text
            text_frame = ctk.CTkFrame(notifications_tab)
            text_frame.pack(fill="x", pady=(0, 20))

            ctk.CTkLabel(text_frame, text="Custom Notification Text",
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

            custom_text_entry = ctk.CTkEntry(text_frame)
            custom_text_entry.pack(fill="x", pady=5)
            custom_text_entry.insert(0, self.settings.get("notification_custom_text", "Your subscription is due soon!"))

            def save_custom_text():
                self.settings["notification_custom_text"] = custom_text_entry.get()
                self.save_settings()

            custom_text_entry.bind("<KeyRelease>", lambda e: save_custom_text())

            # Close button
            ctk.CTkButton(main_frame, text="Close",
                         command=dialog.destroy).pack(pady=20)
            
        def get_color(self, hue, s=0.8, v=0.9):
            rgb = tuple(int(x * 255) for x in colorsys.hsv_to_rgb(hue/360, s, v))
            return "#{:02x}{:02x}{:02x}".format(*rgb)
            
        def apply_color_theme(self, hue):
            main_color = self.get_color(hue)
            hover_color = self.get_color(hue, s=0.7, v=0.8)

            self.settings["hue"] = hue
            self.save_settings()

            # Update all buttons in the application
            def update_button_colors(widget):
                if isinstance(widget, ctk.CTkButton):
                    widget.configure(fg_color=main_color, hover_color=hover_color)
                for child in widget.winfo_children():
                    update_button_colors(child)

            update_button_colors(self)

        def toggle_notification_enabled(self, switch):
            self.settings["notifications_enabled"] = switch.get() == 1
            self.save_settings()

        def toggle_notification_push(self, switch):
            self.settings["notification_push"] = switch.get() == 1
            self.save_settings()

        def update_setting(self, key, value):
            self.settings[key] = value
            self.save_settings()
            
        def update_totals(self):
            monthly_total = 0
            yearly_total = 0
            
            for sub in self.subscriptions:
                if sub['cycle'] == 'Monthly':
                    monthly_total += sub['price']
                    yearly_total += sub['price'] * 12
                else:  # Yearly
                    monthly_total += sub['price'] / 12
                    yearly_total += sub['price']
            
            self.monthly_total.configure(text=f"Monthly Total: ${monthly_total:.2f}")
            self.yearly_total.configure(text=f"Yearly Total: ${yearly_total:.2f}")
        
        def refresh_subscription_list(self):
            # Clear existing items
            for widget in self.main_frame.winfo_children():
                widget.destroy()
                
            self.update_totals()
                
            # Add subscription cards
            for sub in self.subscriptions:
                card = ctk.CTkFrame(self.main_frame)
                card.pack(fill="x", pady=5, padx=5)
                
                # Header frame for icon and name
                header_frame = ctk.CTkFrame(card, fg_color="transparent")
                header_frame.pack(fill="x", pady=5)
                
                # Display icon if available
                if "icon" in sub:
                    try:
                        icon_data = bytes.fromhex(sub["icon"])
                        icon_image = Image.open(io.BytesIO(icon_data))
                        icon_image = icon_image.resize((24, 24))  # Resize icon
                        icon_photo = ctk.CTkImage(light_image=icon_image,
                                                dark_image=icon_image,
                                                size=(24, 24))
                        ctk.CTkLabel(header_frame, image=icon_photo, text="").pack(side="left", padx=5)
                    except Exception as e:
                        print(f"Error loading icon: {e}")
                
                name_label = ctk.CTkLabel(header_frame, text=sub["name"],
                            font=ctk.CTkFont(size=16, weight="bold"))
                name_label.pack(side="left", pady=5)
                
                price_text = f"${sub['price']:.2f} {sub['cycle']}"
                yearly_cost = sub['price'] * (1 if sub['cycle'] == 'Yearly' else 12)
                monthly_cost = sub['price'] * (1/12 if sub['cycle'] == 'Yearly' else 1)
                price_text += f" (${monthly_cost:.2f}/mo, ${yearly_cost:.2f}/yr)"
                ctk.CTkLabel(card, text=price_text).pack()
                
                ctk.CTkLabel(card, text=f"Added: {sub['date_added']}").pack(pady=5)
                
                button_frame = ctk.CTkFrame(card, fg_color="transparent")
                button_frame.pack(pady=5)
                
                if 'website' in sub:
                    def open_website(url=sub['website']):
                        webbrowser.open(url)
                    
                    ctk.CTkButton(button_frame, text="Visit Website",
                                 command=open_website).pack(side="left", padx=5)
                
                def delete_sub(s=sub):
                    confirm = messagebox.askyesno("Delete Subscription",
                                                  f"Are you sure you want to delete {s['name']}?")
                    if confirm:
                        self.subscriptions.remove(s)
                        self.save_subscriptions()
                        self.refresh_subscription_list()
                    
                ctk.CTkButton(button_frame, text="Delete",
                             command=delete_sub,
                             fg_color="red").pack(side="left", padx=5)
        
        def fetch_website_info(self, url):
            """Fetch website title and icon from a given URL."""
            if not url:
                return None, None

            try:
                # Ensure URL has proper scheme
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url

                # Fetch website content
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # Get title
                title = soup.title.string if soup.title else None

                # Get icon
                icon_data = None
                if HAS_FAVICON:
                    icons = favicon.get(url, timeout=5)
                    if icons:
                        # Get the largest icon
                        icon = max(icons, key=lambda x: x.width if x.width else 0)
                        icon_response = requests.get(icon.url, timeout=5)
                        if icon_response.status_code == 200:
                            icon_data = icon_response.content

                return title, icon_data

            except Exception as e:
                print(f"Error fetching website info: {e}")
                return None, None

        def load_settings(self):
            settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
            try:
                with open(settings_path, "r") as f:
                    return json.load(f)
            except FileNotFoundError:
                return {
                    "scaling_factor": 1.0,
                    "appearance_mode": "dark",
                    "hue": 200,  # Default blue-ish hue
                    "notifications_enabled": False,
                    "notification_when": "3 days",
                    "notification_push": False,
                    "notification_custom_text": "Your subscription is due soon!"
                }

        def save_settings(self):
            settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
            with open(settings_path, "w") as f:
                json.dump(self.settings, f)

        def apply_scaling(self, factor):
            ctk.set_widget_scaling(factor)
            ctk.set_window_scaling(factor)

        def save_subscriptions(self):
            subs_path = os.path.join(os.path.dirname(__file__), "subscriptions.json")
            with open(subs_path, "w") as f:
                json.dump(self.subscriptions, f)

        def load_subscriptions(self):
            subs_path = os.path.join(os.path.dirname(__file__), "subscriptions.json")
            try:
                with open(subs_path, "r") as f:
                    self.subscriptions = json.load(f)
            except FileNotFoundError:
                self.subscriptions = []

def load_subscriptions(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "subscriptions.json")
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_subscriptions(subscriptions, path=None):
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "subscriptions.json")
    with open(path, "w") as f:
        json.dump(subscriptions, f)


def run_cli():
    subs = load_subscriptions()
    while True:
        # Calculate totals
        monthly_total = sum(s['price'] if s['cycle'] == 'Monthly' else s['price']/12 for s in subs)
        yearly_total = sum(s['price']*12 if s['cycle'] == 'Monthly' else s['price'] for s in subs)
        
        print("\nSubscriptions:")
        if not subs:
            print("  (no subscriptions)")
        else:
            for i, s in enumerate(subs, 1):
                website_info = f" [{s['website']}]" if 'website' in s else ""
                print(f"  {i}. {s['name']} - ${s['price']:.2f} ({s['cycle']}){website_info}")
                print(f"     Added: {s.get('date_added','?')}")
            
            print(f"\nTotals:")
            print(f"  Monthly: ${monthly_total:.2f}")
            print(f"  Yearly:  ${yearly_total:.2f}")

        print("\nOptions: (a)dd  (d)elete  (o)pen website  (q)uit")
        choice = input("Choose: ").strip().lower()
        if choice in ("q", "quit"):
            save_subscriptions(subs)
            print("Saved. Exiting.")
            break
        if choice in ("a", "add"):
            name = input("Service name: ").strip()
            try:
                price = float(input("Price: ").strip())
            except ValueError:
                print("Invalid price")
                continue
            cycle = input("Billing cycle (Monthly/Yearly) [Monthly]: ").strip() or "Monthly"
            cycle = 'Monthly' if cycle.lower() == 'monthly' else 'Yearly' if cycle.lower() == 'yearly' else 'Monthly'
            website = input("Website URL [optional]: ").strip()
            if website:
                if not website.startswith(('http://', 'https://')):
                    website = 'https://' + website
            
            sub = {
                "name": name,
                "price": price,
                "cycle": cycle,
                "date_added": datetime.now().strftime("%Y-%m-%d"),
                **({"website": website} if website else {})
            }
            subs.append(sub)
            save_subscriptions(subs)
            print("Added.")
        if choice in ("d", "delete"):
            idx_s = input("Index to delete: ").strip()
            try:
                idx = int(idx_s) - 1
                if 0 <= idx < len(subs):
                    removed = subs.pop(idx)
                    save_subscriptions(subs)
                    print(f"Removed {removed['name']}")
                else:
                    print("Index out of range")
            except ValueError:
                print("Invalid index")
        if choice in ("o", "open"):
            idx_s = input("Index to open website: ").strip()
            try:
                idx = int(idx_s) - 1
                if 0 <= idx < len(subs):
                    sub = subs[idx]
                    if 'website' in sub:
                        webbrowser.open(sub['website'])
                        print(f"Opening website for {sub['name']}...")
                    else:
                        print("No website URL saved for this subscription")
                else:
                    print("Index out of range")
            except ValueError:
                print("Invalid index")

if __name__ == "__main__":
    if HAS_TK:
        app = SubscriptionTracker()
        app.mainloop()
    else:
        run_cli()