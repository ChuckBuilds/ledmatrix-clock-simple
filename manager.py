"""
Simple Clock Plugin for LEDMatrix

Displays current time and date with customizable formatting and colors.
Migrated from the original clock.py manager as a plugin example.

API Version: 1.0.0
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any, Tuple
from src.plugin_system.base_plugin import BasePlugin

try:
    import pytz
except ImportError:
    pytz = None


class SimpleClock(BasePlugin):
    """
    Simple clock plugin that displays current time and date.

    Configuration options:
        timezone (str): Timezone for display (default: UTC)
        time_format (str): 12h or 24h format (default: 12h)
        show_seconds (bool): Show seconds in time (default: False)
        show_date (bool): Show date below time (default: True)
        date_format (str): Date format (default: MM/DD/YYYY)
        time_color (list): RGB color for time [R, G, B] (default: [255, 255, 255])
        date_color (list): RGB color for date [R, G, B] (default: [255, 128, 64])
        ampm_color (list): RGB color for AM/PM [R, G, B] (default: [255, 255, 128])
        position (dict): X,Y position for display (default: 0,0)
        display_style (str): 'standard' for text, 'seven_segment' for digital
        segment_color (list): RGB color for seven-segment display segments
    """

    def __init__(self, plugin_id: str, config: Dict[str, Any],
                 display_manager, cache_manager, plugin_manager):
        """Initialize the clock plugin."""
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)

        # Clock-specific configuration
        # Use plugin-specific timezone, or fall back to global timezone, or default to UTC
        self.timezone_str = config.get('timezone') or self._get_global_timezone() or 'UTC'
        self.time_format = config.get('time_format', '12h')
        self.show_seconds = config.get('show_seconds', False)
        self.show_date = config.get('show_date', True)
        self.date_format = config.get('date_format', 'OLD_CLOCK')
        self.display_style = config.get('display_style', 'standard')

        # Colors - convert to integers in case they come from JSON as strings
        time_color_raw = config.get('time_color', [255, 255, 255])
        date_color_raw = config.get('date_color', [255, 128, 64])
        ampm_color_raw = config.get('ampm_color', [255, 255, 128])
        segment_color_raw = config.get('segment_color', [255, 255, 255])
        
        self.time_color = tuple(int(c) for c in time_color_raw)
        self.date_color = tuple(int(c) for c in date_color_raw)
        self.ampm_color = tuple(int(c) for c in ampm_color_raw)
        self.segment_color = tuple(int(c) for c in segment_color_raw)

        # Position - use flattened keys
        self.pos_x = config.get('position_x', 0)
        self.pos_y = config.get('position_y', 0)

        # Get timezone
        self.timezone = self._get_timezone()

        # Track last display for optimization
        self.last_time_str = None
        self.last_ampm_str = None
        self.last_date_str = None
        self.last_weekday_str = None

        self.logger.info(f"Clock plugin initialized for timezone: {self.timezone_str}")

    def _get_global_timezone(self) -> str:
        """Get the global timezone from the main config."""
        try:
            # Access the main config through the plugin manager's config_manager
            if hasattr(self.plugin_manager, 'config_manager') and self.plugin_manager.config_manager:
                main_config = self.plugin_manager.config_manager.load_config()
                return main_config.get('timezone', 'UTC')
        except Exception as e:
            self.logger.warning(f"Error getting global timezone: {e}")
        return 'UTC'

    def _get_timezone(self):
        """Get timezone from configuration."""
        if pytz is None:
            self.logger.warning("pytz not available, using UTC timezone only")
            return None

        try:
            return pytz.timezone(self.timezone_str)
        except Exception:
            self.logger.warning(
                f"Invalid timezone '{self.timezone_str}'. Falling back to UTC. "
                "Valid timezones can be found at: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
            )
            return pytz.utc

    def _format_time_12h(self, dt: datetime) -> Tuple[str, str]:
        """Format time in 12-hour format."""
        time_str = dt.strftime("%I:%M")
        if self.show_seconds:
            time_str += dt.strftime(":%S")

        # Remove leading zero from hour
        if time_str.startswith("0"):
            time_str = time_str[1:]

        ampm = dt.strftime("%p")
        return time_str, ampm

    def _format_time_24h(self, dt: datetime) -> str:
        """Format time in 24-hour format."""
        time_str = dt.strftime("%H:%M")
        if self.show_seconds:
            time_str += dt.strftime(":%S")
        return time_str

    def _get_ordinal_suffix(self, day: int) -> str:
        """Get the ordinal suffix for a day number (1st, 2nd, 3rd, etc.)."""
        if 10 <= day % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        return suffix

    def _format_date(self, dt: datetime) -> str:
        """Format date according to configured format."""
        if self.date_format == "MM/DD/YYYY":
            return dt.strftime("%m/%d/%Y")
        elif self.date_format == "DD/MM/YYYY":
            return dt.strftime("%d/%m/%Y")
        elif self.date_format == "YYYY-MM-DD":
            return dt.strftime("%Y-%m-%d")
        elif self.date_format == "OLD_CLOCK":
            # Match old clock format: "Month Day" with ordinal suffix
            day_suffix = self._get_ordinal_suffix(dt.day)
            return dt.strftime(f'%B %d{day_suffix}')
        else:
            return dt.strftime("%m/%d/%Y")  # fallback

    def update(self) -> None:
        """
        Update clock data.

        For a clock, we don't need to fetch external data, but we can
        prepare the current time for display optimization.
        """
        try:
            # Get current time
            if pytz and self.timezone:
                # Use timezone-aware datetime
                utc_now = datetime.now(pytz.utc)
                local_time = utc_now.astimezone(self.timezone)
            else:
                # Use local system time (no timezone conversion)
                local_time = datetime.now()
            
            # Store local_time for date formatting access
            self.current_dt = local_time

            if self.time_format == "12h":
                new_time, new_ampm = self._format_time_12h(local_time)
                # Only log if the time actually changed
                if not hasattr(self, 'current_time') or new_time != self.current_time:
                    if not hasattr(self, '_last_time_log') or time.time() - getattr(self, '_last_time_log', 0) > 60:
                        self.logger.info(f"Clock updated: {new_time} {new_ampm}")
                        self._last_time_log = time.time()
                self.current_time = new_time
                self.current_ampm = new_ampm
            else:
                new_time = self._format_time_24h(local_time)
                if not hasattr(self, 'current_time') or new_time != self.current_time:
                    if not hasattr(self, '_last_time_log') or time.time() - getattr(self, '_last_time_log', 0) > 60:
                        self.logger.info(f"Clock updated: {new_time}")
                        self._last_time_log = time.time()
                self.current_time = new_time

            if self.show_date:
                self.current_date = self._format_date(local_time)
                # Also get weekday for old clock layout
                self.current_weekday = local_time.strftime('%A')

            self.last_update = time.time()

        except Exception as e:
            self.logger.error(f"Error updating clock: {e}")

    # --- Seven-Segment Helper Methods ---

    def _draw_segment(self, x: int, y: int, width: int, height: int, color: Tuple[int, int, int]) -> None:
        """Draw a single segment."""
        # Use rectangle for segments
        self.display_manager.draw.rectangle([x, y, x + width - 1, y + height - 1], fill=color)

    def _get_segment_patterns(self) -> Dict[str, list]:
        """
        Get segment patterns for digits and letters.
        Segments:
             a
           f   b
             g
           e   c
             d
        """
        return {
            '0': ['a', 'b', 'c', 'd', 'e', 'f'],
            '1': ['b', 'c'],
            '2': ['a', 'b', 'g', 'e', 'd'],
            '3': ['a', 'b', 'g', 'c', 'd'],
            '4': ['f', 'g', 'b', 'c'],
            '5': ['a', 'f', 'g', 'c', 'd'],
            '6': ['a', 'f', 'g', 'c', 'd', 'e'],
            '7': ['a', 'b', 'c'],
            '8': ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
            '9': ['a', 'b', 'c', 'f', 'g'],
            'A': ['a', 'b', 'c', 'e', 'f', 'g'],
            'P': ['a', 'b', 'e', 'f', 'g'],
            'M': ['a', 'b', 'c', 'e', 'f'], # Approximation for M
        }

    def _calculate_segment_dimensions(self) -> Dict[str, int]:
        """Calculate dimensions based on display size."""
        width = self.display_manager.width
        
        # Scale thickness based on width, but keep it reasonable
        thickness = max(1, min(3, width // 32))
        
        # Digit dimensions
        # For 64px width, we want digits to fit comfortably.
        # Approx 4 digits + colon + spacing
        digit_width = width // 6 
        digit_height = int(digit_width * 1.6) # Keep aspect ratio
        
        # Ensure minimum height on small displays
        if digit_height < 10:
            digit_height = 10
            digit_width = int(digit_height / 1.6)

        # Calculate segment lengths based on thickness
        h_seg_len = digit_width - (2 * thickness)
        v_seg_len = (digit_height - (3 * thickness)) // 2

        return {
            'thickness': thickness,
            'width': digit_width,
            'height': digit_height,
            'h_len': h_seg_len,
            'v_len': v_seg_len,
            'spacing': thickness + 1
        }

    def _draw_seven_segment_digit(self, char: str, x: int, y: int, color: Tuple[int, int, int]) -> None:
        """Render a single seven-segment digit."""
        dims = self._calculate_segment_dimensions()
        t = dims['thickness']
        w = dims['width']
        h_len = dims['h_len']
        v_len = dims['v_len']
        
        patterns = self._get_segment_patterns()
        segments = patterns.get(char, [])
        
        # Coordinates for segments
        # a: top
        if 'a' in segments:
            self._draw_segment(x + t, y, h_len, t, color)
        # b: top-right
        if 'b' in segments:
            self._draw_segment(x + w - t, y + t, t, v_len, color)
        # c: bottom-right
        if 'c' in segments:
            self._draw_segment(x + w - t, y + 2*t + v_len, t, v_len, color)
        # d: bottom
        if 'd' in segments:
            self._draw_segment(x + t, y + 2*v_len + 2*t, h_len, t, color)
        # e: bottom-left
        if 'e' in segments:
            self._draw_segment(x, y + 2*t + v_len, t, v_len, color)
        # f: top-left
        if 'f' in segments:
            self._draw_segment(x, y + t, t, v_len, color)
        # g: middle
        if 'g' in segments:
            self._draw_segment(x + t, y + t + v_len, h_len, t, color)

    def _draw_seven_segment_colon(self, x: int, y: int, color: Tuple[int, int, int]) -> int:
        """Draw colon separator."""
        dims = self._calculate_segment_dimensions()
        t = dims['thickness']
        h = dims['height']
        
        # Draw two dots
        dot_size = t
        
        # Top dot
        self._draw_segment(x, y + h//3, dot_size, dot_size, color)
        # Bottom dot
        self._draw_segment(x, y + 2*h//3, dot_size, dot_size, color)
        
        return dot_size + 2 # Return width used

    def _draw_seven_segment_time(self, time_str: str, ampm_str: str, start_x: int, start_y: int, color: Tuple[int, int, int]) -> int:
        """Render complete time string in seven-segment."""
        dims = self._calculate_segment_dimensions()
        char_width = dims['width']
        spacing = dims['spacing']
        
        current_x = start_x
        
        for char in time_str:
            if char == ':':
                colon_width = self._draw_seven_segment_colon(current_x, start_y, color)
                current_x += colon_width + spacing
            elif char.isdigit():
                self._draw_seven_segment_digit(char, current_x, start_y, color)
                current_x += char_width + spacing
                
        return current_x - start_x # Total width

    def _format_date_for_seven_segment(self, dt: datetime) -> str:
        """Format date as 'Wed Nov 19'."""
        # %a = Abbreviated weekday (Wed)
        # %b = Abbreviated month (Nov)
        # %d = Day of month (19)
        # Use %d instead of %-d for Windows compatibility, strip leading zero manually
        day = dt.strftime("%d").lstrip("0")
        return f"{dt.strftime('%a %b')} {day}"

    def _display_seven_segment(self, force_clear: bool = False) -> None:
        """Main seven-segment display method."""
        # Clear display
        self.display_manager.clear()
        
        dims = self._calculate_segment_dimensions()
        digit_width = dims['width']
        spacing = dims['spacing']
        total_height = dims['height']
        
        # Calculate total width of time string to center it
        # Digits + colon + spacing
        time_str = getattr(self, 'current_time', '00:00')
        ampm_str = getattr(self, 'current_ampm', '')
        
        num_digits = sum(c.isdigit() for c in time_str)
        num_colons = time_str.count(':')
        
        # Estimate width
        colon_width = dims['thickness'] + 2
        estimated_width = (num_digits * digit_width) + (num_digits * spacing) + (num_colons * (colon_width + spacing))
        
        # Calculate start X to center
        start_x = (self.display_manager.width - estimated_width) // 2
        start_y = 4 # Top margin
        
        # Draw time
        self._draw_seven_segment_time(time_str, ampm_str, start_x, start_y, self.segment_color)
        
        # Draw date below
        if self.show_date and hasattr(self, 'current_dt'):
            date_str = self._format_date_for_seven_segment(self.current_dt)
            
            # Center date text
            # Standard font size is approx 8px height
            date_y = start_y + total_height + 4 
            
            # Check if it fits on screen vertically
            if date_y + 8 <= self.display_manager.height:
                self.display_manager.draw_text(
                    date_str,
                    y=date_y,
                    color=self.date_color,
                    small_font=True,
                    centered=True
                )
        
        self.display_manager.update_display()
        
        # Update last displayed tracking (reuse standard tracking vars for simplicity)
        self.last_time_str = time_str

    def display(self, force_clear: bool = False) -> None:
        """
        Display the clock.

        Args:
            force_clear: If True, clear display before rendering
        """
        try:
            # Ensure update() has been called at least once
            if not hasattr(self, 'current_time'):
                self.logger.warning("Clock display called before update() - calling update() now")
                self.update()
            else:
                # Update time to check if it has changed
                self.update()
            
            # Routing based on display style
            if self.display_style == 'seven_segment':
                # Check for changes - simplified check for now
                current_time_str = getattr(self, 'current_time', '')
                if not force_clear and current_time_str == self.last_time_str:
                    return
                self._display_seven_segment(force_clear)
                return

            # Check if time/date has changed since last display
            current_time_str = getattr(self, 'current_time', '')
            current_ampm_str = getattr(self, 'current_ampm', '') if self.time_format == "12h" else ''
            current_date_str = getattr(self, 'current_date', '') if self.show_date else ''
            current_weekday_str = getattr(self, 'current_weekday', '') if (self.show_date and self.date_format == "OLD_CLOCK") else ''
            
            # Build comparison string that includes time and AM/PM (if applicable)
            current_display_str = f"{current_time_str} {current_ampm_str}".strip()
            last_display_str = f"{self.last_time_str} {getattr(self, 'last_ampm_str', '')}".strip() if self.last_time_str else ''
            
            # Determine if we need to redraw
            needs_redraw = force_clear or (
                current_display_str != last_display_str or
                current_date_str != self.last_date_str or
                current_weekday_str != getattr(self, 'last_weekday_str', '')
            )
            
            if not needs_redraw:
                return

            # Clear the display unconditionally if we are drawing
            self.display_manager.clear()

            # Get display dimensions
            width = self.display_manager.width
            height = self.display_manager.height
            
            # Layout logic from old_managers/clock.py
            
            # Draw time (large, centered, near top)
            self.display_manager.draw_text(
                self.current_time,
                y=4,  # Move up slightly to make room for two lines of date
                color=self.time_color,
                small_font=True
            )

            # Display AM/PM indicator (12h format only) - positioned next to time
            if self.time_format == "12h" and hasattr(self, 'current_ampm'):
                # Calculate AM/PM position: to the right of centered time
                try:
                    # Try to use font from display_manager if available
                    time_width = self.display_manager.font.getlength(self.current_time)
                except (AttributeError, TypeError):
                    # Fallback calculation
                    time_width = len(self.current_time) * 6  # Approximate width
                
                ampm_x = (width + time_width) // 2 + 4
                self.display_manager.draw_text(
                    self.current_ampm,
                    x=ampm_x,
                    y=4,  # Align with time
                    color=self.ampm_color,
                    small_font=True
                )

            # Display date
            if self.show_date and hasattr(self, 'current_date'):
                if self.date_format == "OLD_CLOCK" and hasattr(self, 'current_weekday'):
                    # Weekday on first line
                    self.display_manager.draw_text(
                        self.current_weekday,
                        y=height - 18,  # First line of date
                        color=self.date_color,
                        small_font=True
                    )
                    # Month and day on second line
                    self.display_manager.draw_text(
                        self.current_date,
                        y=height - 9,  # Second line of date
                        color=self.date_color,
                        small_font=True
                    )
                else:
                    # Other date formats: single line centered below time
                    # Use approximate position similar to old clock but just one line
                    self.display_manager.draw_text(
                        self.current_date,
                        y=height - 9,
                        color=self.date_color,
                        small_font=True
                    )

            # Update the physical display
            self.display_manager.update_display()
            
            # Track what we just displayed
            self.last_time_str = current_time_str
            if self.time_format == "12h":
                self.last_ampm_str = current_ampm_str
            self.last_date_str = current_date_str
            if self.show_date and self.date_format == "OLD_CLOCK":
                self.last_weekday_str = current_weekday_str
            
            self.logger.debug(f"Clock displayed: {current_display_str} {current_date_str}")

        except Exception as e:
            self.logger.error(f"Error displaying clock: {e}", exc_info=True)
            # Show error message on display
            try:
                self.display_manager.clear()
                self.display_manager.draw_text(
                    "Clock Error",
                    x=5, y=15,
                    color=(255, 0, 0)
                )
                self.display_manager.update_display()
            except:
                pass  # If display fails, don't crash

    def get_display_duration(self) -> float:
        """Get display duration from config."""
        return self.config.get('display_duration', 15.0)

    def validate_config(self) -> bool:
        """Validate plugin configuration."""
        # Call parent validation first
        if not super().validate_config():
            return False

        # Validate display style
        if self.display_style not in ["standard", "seven_segment"]:
            self.logger.error(f"Invalid display_style: {self.display_style}")
            return False

        # Validate timezone
        if pytz is not None:
            try:
                pytz.timezone(self.timezone_str)
            except Exception:
                self.logger.error(f"Invalid timezone: {self.timezone_str}")
                return False
        else:
            self.logger.warning("pytz not available, timezone validation skipped")

        # Validate time format
        if self.time_format not in ["12h", "24h"]:
            self.logger.error(f"Invalid time format: {self.time_format}")
            return False

        # Validate date format
        if self.date_format not in ["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD", "OLD_CLOCK"]:
            self.logger.error(f"Invalid date format: {self.date_format}")
            return False

        # Validate colors
        for color_name, color_value in [
            ("time_color", self.time_color),
            ("date_color", self.date_color),
            ("ampm_color", self.ampm_color),
            ("segment_color", self.segment_color)
        ]:
            if not isinstance(color_value, tuple) or len(color_value) != 3:
                self.logger.error(f"Invalid {color_name}: must be RGB tuple")
                return False
            try:
                # Convert to integers and validate range
                color_ints = [int(c) for c in color_value]
                if not all(0 <= c <= 255 for c in color_ints):
                    self.logger.error(f"Invalid {color_name}: values must be 0-255")
                    return False
            except (ValueError, TypeError):
                self.logger.error(f"Invalid {color_name}: values must be numeric")
                return False

        return True

    def get_info(self) -> Dict[str, Any]:
        """Return plugin info for web UI."""
        info = super().get_info()
        info.update({
            'current_time': getattr(self, 'current_time', None),
            'timezone': self.timezone_str,
            'time_format': self.time_format,
            'show_seconds': self.show_seconds,
            'show_date': self.show_date,
            'date_format': self.date_format,
            'display_style': self.display_style
        })
        return info
