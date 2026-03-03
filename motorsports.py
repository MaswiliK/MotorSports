import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import pytz
import schedule
import time
import threading
from icalendar import Calendar as iCalendar
from pathlib import Path
import logging
from tkcalendar import Calendar as tkCalendar
from win10toast import ToastNotifier


eat_tz = pytz.timezone("Africa/Nairobi")

# Constants
ICS_FILES = {
    "F1": Path(r"C:\Users\hp\Documents\Projects\SCRIPTS\MotorSports\ics\calendar-formula-2026.ics"),
    "MotoGP": Path(r"C:\Users\hp\Documents\Projects\SCRIPTS\MotorSports\ics\MotoGP_2026_calendar.ics"),
    "WorldSBK": Path(r"C:\Users\hp\Documents\Projects\SCRIPTS\MotorSports\ics\WorldSBK_2026_calendar.ics")
}

SERIES_COLORS = {
    "F1": "#FF4C4C",  # Red for F1
    "MotoGP": "#4C84FF",  # Blue for MotoGP
    "WorldSBK": "#4CFF4C"  # Green for WSBK
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('motorsport_tracker.log'), logging.StreamHandler()]
)

class MotorsportTracker:
    def __init__(self, root):
        self.root = root
        self.next_event = None
        self.toaster = ToastNotifier()
        self.setup_ui()
        self.start_background_tasks()
        
    def setup_ui(self):
        """Set up the user interface"""
        self.root.title("Motorsport Event Tracker")
        self.root.geometry("1100x650")
        self.root.minsize(900, 550)
        
        # Configure styles
        self.style = ttk.Style()
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("Timer.TLabel", font=("Consolas", 12, "bold"))
        self.style.configure("NextRace.TLabel", font=("Arial", 10, "bold"))
        
        # Main container
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(expand=True, fill="both")
        
        # Left panel (events list)
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side="left", fill="both", expand=True, padx=5)
        
        # Right panel (calendar and timer)
        right_panel = ttk.Frame(main_frame, width=300)
        right_panel.pack(side="right", fill="y", padx=5)

        # Calendar Frame
        self.cal_frame = ttk.LabelFrame(right_panel, text="Event Calendar", padding=10)
        self.cal_frame.pack(fill="both", pady=(0, 15))
        
        # Initialize calendar
        self.calendar_widget = tkCalendar(
            self.cal_frame,
            selectmode='day',
            year=datetime.datetime.now().year,
            month=datetime.datetime.now().month,
            day=datetime.datetime.now().day,
            showweeknumbers=False,
            date_pattern='y-mm-dd'
        )
        self.calendar_widget.pack(fill="both", expand=True)
        self.calendar_widget.bind('<<CalendarSelected>>', self.on_date_selected)

        # Timer Frame
        timer_frame = ttk.LabelFrame(right_panel, text="Next Race", padding=10)
        timer_frame.pack(fill="x", pady=5)
        
        # Next race info
        self.next_race_info = ttk.Label(
            timer_frame,
            text="No upcoming races",
            style="NextRace.TLabel",
            wraplength=250
        )
        self.next_race_info.pack(anchor="w", pady=(0, 10))
        
        # Countdown timer
        self.timer_var = tk.StringVar(value="00:00:00")
        self.timer_label = ttk.Label(
            timer_frame,
            textvariable=self.timer_var,
            style="Timer.TLabel",
            foreground="#FF4C4C",
            anchor="center"
        )
        self.timer_label.pack(fill="x", pady=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(
            timer_frame,
            orient="horizontal",
            length=250,
            mode="determinate"
        )
        self.progress.pack(fill="x", pady=5)
        
        # Events table setup
        self.setup_events_table(left_panel)
        
        # Status Bar (add this at the end of the method, before the final update call)
        status_bar = ttk.Frame(self.root, height=25, relief="sunken")
        status_bar.pack(fill="x", side="bottom", pady=(5, 0))
        
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(
            status_bar,
            textvariable=self.status_var,
            anchor="w"
        )
        status_label.pack(fill="x", padx=5)
        
        self.update_timer()
        # Initial data load
        self.update_event_list()
        
    
    def setup_events_table(self, parent):
        """Configure the events table"""
        # Filter controls
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill="x", pady=5)
        
        # Series filter
        ttk.Label(filter_frame, text="Filter:").pack(side="left", padx=(0, 5))
        self.series_var = tk.StringVar(value="All")
        series_dropdown = ttk.Combobox(
            filter_frame,
            textvariable=self.series_var,
            values=["All", "F1", "MotoGP", "WorldSBK"],
            state="readonly",
            width=8
        )
        series_dropdown.pack(side="left")
        series_dropdown.bind("<<ComboboxSelected>>", lambda e: self.update_event_list())
        
        # Race-only filter
        self.filter_var = tk.BooleanVar()
        ttk.Checkbutton(
            filter_frame,
            text="Races Only",
            variable=self.filter_var,
            command=self.update_event_list
        ).pack(side="left", padx=10)
        
        # Refresh button
        ttk.Button(
            filter_frame,
            text="Refresh",
            command=self.update_event_list
        ).pack(side="right")
        
        # Events table
        table_frame = ttk.Frame(parent)
        table_frame.pack(expand=True, fill="both")
        
        columns = ("Series", "Event", "Location", "Date & Time")
        self.event_table = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=15
        )
        
        # Configure columns
        col_widths = [80, 250, 150, 120]
        for col, width in zip(columns, col_widths):
            self.event_table.heading(col, text=col)
            self.event_table.column(col, width=width, anchor="center")
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.event_table.yview)
        self.event_table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.event_table.pack(expand=True, fill="both")
        
        # Apply row colors
        for color in SERIES_COLORS.values():
            self.event_table.tag_configure(color, foreground=color)
    
    def fetch_calendar_from_file(self, file_path):
        """Fetch calendar from a local ICS file"""
        try:
            with open(file_path, 'rb') as f:
                cal_data = f.read()
            return iCalendar.from_ical(cal_data)  # Using renamed import
        except Exception as e:
            logging.error(f"Error reading calendar file {file_path}: {e}")
            return None
    
    def get_upcoming_events(self, cal, days_ahead=7, filter_race_only=False):
        """Extract upcoming events from a calendar"""
        upcoming = []
        now = datetime.datetime.now(eat_tz)
        
        if not cal:
            return upcoming
            
        for component in cal.walk():
            if component.name == "VEVENT":
                summary = str(component.get('summary', ''))
                if filter_race_only and not any(x in summary.upper() for x in ["RAC", "RACE"]):
                    continue  # Skip non-race events
                
                event_start = component.get('dtstart').dt
                if isinstance(event_start, datetime.date) and not isinstance(event_start, datetime.datetime):
                    event_start = datetime.datetime.combine(event_start, datetime.time(0, 0), tzinfo=eat_tz)
                
                if now <= event_start <= now + datetime.timedelta(days=days_ahead):
                    location = str(component.get('location', 'No location provided'))
                    upcoming.append({
                        'summary': summary,
                        'start': event_start,
                        'location': location
                    })
        
        upcoming.sort(key=lambda x: x['start'])
        return upcoming
    
    def update_timer(self):
        """Update the countdown timer and progress bar every second"""
        if hasattr(self, 'next_event') and self.next_event:
            now = datetime.datetime.now(eat_tz)
            time_diff = self.next_event['start'] - now
            
            if time_diff.total_seconds() > 0:
                # Update timer display
                days = time_diff.days
                hours, remainder = divmod(time_diff.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if days > 0:
                    self.timer_var.set(f"{days}d {hours:02}:{minutes:02}:{seconds:02}")
                else:
                    self.timer_var.set(f"{hours:02}:{minutes:02}:{seconds:02}")
                
                # Update progress bar
                if hasattr(self.next_event, 'found_time'):
                    total_hours = (self.next_event['start'] - self.next_event['found_time']).total_seconds()
                    elapsed = (now - self.next_event['found_time']).total_seconds()
                    progress_value = min(100, (elapsed / total_hours) * 100)
                    self.progress['value'] = progress_value
                    
                # Color changes based on urgency
                if time_diff.total_seconds() < 3600:  # Less than 1 hour
                    self.timer_label.configure(foreground="#FF0000")
                elif time_diff.total_seconds() < 86400:  # Less than 1 day
                    self.timer_label.configure(foreground="#FF6B00")
            else:
                self.timer_var.set("LIVE NOW!")
                self.timer_label.configure(foreground="#00AA00")
                self.progress['value'] = 100
                self.next_event = None
        
        # Schedule next update
        self.root.after(1000, self.update_timer)

    def on_date_selected(self, event):
        """Handle calendar date selection"""
        selected_date = self.calendar_widget.get_date()
        self.event_table.delete(*self.event_table.get_children())
        
        # Filter events for selected date
        for name, file_path in ICS_FILES.items():
            if self.series_var.get() != "All" and name != self.series_var.get():
                continue
                
            cal = self.fetch_calendar_from_file(file_path)
            if cal:
                events = self.get_upcoming_events(cal, days_ahead=365)
                for event in events:
                    event_date = event['start'].astimezone(eat_tz).date()
                    if str(event_date) == selected_date:
                        if self.filter_var.get() and "Race" not in event['summary']:
                            continue
                            
                        tag_color = SERIES_COLORS.get(name, "black")
                        self.event_table.insert('', 'end', values=(
                            name, 
                            event['summary'], 
                            event['location'], 
                            event['start'].astimezone(eat_tz).strftime("%Y-%m-%d %H:%M")
                        ), tags=(tag_color,))

    def update_calendar_markers(self):
        """Update calendar with event markers using a bullet point approach"""
        # Store current selection
        current_date = self.calendar_widget.get_date()
        
        # Recreate the calendar widget
        for widget in self.cal_frame.winfo_children():
            widget.destroy()
        
        self.calendar_widget = tkCalendar(
            self.cal_frame,
            selectmode='day',
            year=datetime.datetime.now().year,
            month=datetime.datetime.now().month,
            day=datetime.datetime.now().day,
            showweeknumbers=False,
            date_pattern='y-mm-dd'
        )
        self.calendar_widget.pack(fill='both', expand=True)
        self.calendar_widget.bind('<<CalendarSelected>>', self.on_date_selected)
        self.calendar_widget.selection_set(current_date)

        # Get all events
        all_events = []
        for name, file_path in ICS_FILES.items():
            cal = self.fetch_calendar_from_file(file_path)
            if cal:
                events = self.get_upcoming_events(cal, days_ahead=365, filter_race_only=self.filter_var.get())
                all_events.extend(events)

        # Update next event timer
        if all_events:
            upcoming_events = [e for e in all_events if e['start'] > datetime.datetime.now(eat_tz)]
            if upcoming_events:
                self.next_event = min(upcoming_events, key=lambda x: x['start'])
                self.next_event['found_time'] = datetime.datetime.now(eat_tz)
                self.next_race_info.config(text=f"{self.next_event['summary']}\n{self.next_event['start'].strftime('%b %d, %H:%M')}")

        # Mark events using a different approach
        for event in all_events:
            event_date = event['start'].astimezone(eat_tz).date()
            try:
                # Get the day label from the calendar's children
                for child in self.calendar_widget.winfo_children():
                    if hasattr(child, 'children'):
                        for day_label in child.winfo_children():
                            if hasattr(day_label, 'date') and day_label.date == event_date:
                                # Add a bullet point to the date text
                                day_label.configure(text=f"{day_label.date.day} •")
                                day_label.configure(foreground=SERIES_COLORS["F1"])
            except Exception as e:
                logging.debug(f"Couldn't mark date {event_date}: {e}")

    def update_event_list(self):
        """Update both event list and calendar markers"""
        try:
            selected_series = self.series_var.get()
            race_only = self.filter_var.get()
            self.event_table.delete(*self.event_table.get_children())
            
            for name, file_path in ICS_FILES.items():
                if selected_series != "All" and name != selected_series:
                    continue
                
                cal = self.fetch_calendar_from_file(file_path)
                if cal:
                    events = self.get_upcoming_events(cal, filter_race_only=race_only)
                    for event in events:
                        tag_color = SERIES_COLORS.get(name, "black")
                        local_time = event['start'].astimezone(eat_tz).strftime("%Y-%m-%d %H:%M")
                        self.event_table.insert('', 'end', values=(
                            name, 
                            event['summary'], 
                            event['location'], 
                            local_time
                        ), tags=(tag_color,))
            
            self.update_calendar_markers()
            if hasattr(self, 'status_var'):  # Safe check
                self.status_var.set(f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            logging.error(f"Error updating event list: {e}")
            if hasattr(self, 'status_var'):  # Safe check
                self.status_var.set("Error updating events")

    def notify_upcoming_race(self):
        """Show desktop notification for upcoming races"""
        try:
            upcoming_races = []
            now = datetime.datetime.now(eat_tz)
            
            for name, file_path in ICS_FILES.items():
                cal = self.fetch_calendar_from_file(file_path)
                if cal:
                    events = self.get_upcoming_events(cal, days_ahead=1, filter_race_only=True)
                    for event in events:
                        if now <= event['start'] <= now + datetime.timedelta(hours=1):
                            local_time = event['start'].astimezone(eat_tz).strftime('%H:%M')
                            upcoming_races.append(f"{name}: {event['summary']} at {local_time}")
            
            if upcoming_races:
                # Show desktop notification
                self.toaster.show_toast(
                    "🏁 Upcoming Motorsport Events",
                    "\n".join(upcoming_races),
                    duration=10,
                    threaded=True,
                    icon_path=None
                )
                
        except Exception as e:
            logging.error(f"Error in notification check: {e}")

    def start_background_tasks(self):
        """Start background tasks for notifications and auto-refresh"""
        # Schedule notifications
        schedule.every(30).minutes.do(self.notify_upcoming_race)
        
        # Start scheduler in background thread
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(10)
        
        threading.Thread(target=run_scheduler, daemon=True).start()
        
        # Auto-refresh every 5 minutes
        def auto_refresh():
            self.update_event_list()
            self.root.after(300000, auto_refresh)  # 300000 ms = 5 minutes
        
        self.root.after(300000, auto_refresh)
def main():
    root = tk.Tk()
    try:
        root.iconbitmap(default='motorsport.ico')
    except:
        pass
        
    app = MotorsportTracker(root)
    
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit the Motorsport Event Tracker?"):
            root.quit()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main() 