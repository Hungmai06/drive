"""
GOOGLE DRIVE DOWNLOADER - SIMPLE GUI
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import requests
import os
import re
import threading
import subprocess
from http.cookiejar import MozillaCookieJar
from queue import Queue
import json
import time

class SimpleDriveDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("🚀 Google Drive Downloader Pro")
        self.root.geometry("1000x650")
        self.root.configure(bg="#f0f0f0")
        
        self.cookies_file = ""
        self.output_folder = os.getcwd()
        self._session = None
        self._session_cookie_path = None
        self.scan_delay = 0.0
        self.scan_root_folder_name = ""
        self.download_queue = Queue()
        self.active_downloads = 0
        self.max_concurrent = 5
        self.file_list = []
        self.log_queue = Queue()
        self.pending_files = []
        self.file_progress = {}
        self.file_tree_items = {}
        
        # Danh sách file cần loại trừ
        self.excluded_filenames = [
            "0. khoahocgiahoi.com website bán khóa học uy tín, chất lượng, giá rẻ",
            "0. khoahocgiahoi.com website bán khóa học uy tín, chất lượng, giá rẻ.txt",
            "0. website bán khóa học uy tín, chất lượng, giá rẻ",
            "0. website bán khóa học uy tín, chất lượng, giá rẻ.txt",
            "Bản sao của Bài 12 #2.3 Tao CV Chuyen Nghiep voi TopCV.mp4",
            "Truy Cập Nhanh - Danh Sách Khóa Học (Khóa Học Giá Hời).xlsx",
            "website bán khóa học uy tín, chất lượng, giá rẻ",
            "Danh Sách Khóa Học (Khóa Học Giá Hời).xlsx",
            "NHÓM ZALO - QUÉT MÃ QR VÀO NHÓM",
            "NHÓM ZALO HỖ TRỢ KHÁCH HÀNG - QUÉT MÃ QR VÀO NHÓM.png",
        ]
        
        self.setup_ui()
        self.process_log_queue()

    def _subprocess_no_window_kwargs(self):
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = startupinfo
        return kwargs
    
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="8")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title = tk.Label(main_frame, text="🚀 Drive Downloader Pro", 
                        font=('Segoe UI', 14, 'bold'), bg="#f0f0f0", fg="#1a73e8")
        title.pack(pady=(0, 8))
        
        # LAYOUT: Chia 2 cột
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # ===== LEFT SIDE: Controls =====
        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        
        # Notebook (Tabs)
        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Single Download
        self.tab_single = ttk.Frame(self.notebook, padding="6")
        self.notebook.add(self.tab_single, text="📥 1 File")
        self.setup_single_tab()
        
        # Tab 2: Folder Download
        self.tab_folder = ttk.Frame(self.notebook, padding="6")
        self.notebook.add(self.tab_folder, text="📁 Folder")
        self.setup_folder_tab()
        
        # Settings
        settings_frame = ttk.LabelFrame(left_frame, text="⚙️ Cài đặt", padding="6")
        settings_frame.pack(fill=tk.X, pady=(6, 4))
        
        settings_grid = ttk.Frame(settings_frame)
        settings_grid.pack(fill=tk.X)
        
        # Cookies
        ttk.Label(settings_grid, text="🍪", font=('Segoe UI', 9)).grid(row=0, column=0, sticky=tk.W, padx=2)
        self.cookies_var = tk.StringVar()
        ttk.Entry(settings_grid, textvariable=self.cookies_var, width=28, state='readonly', font=('Segoe UI', 8)).grid(row=0, column=1, padx=2)
        ttk.Button(settings_grid, text="Chọn", command=self.choose_cookies, width=6).grid(row=0, column=2, padx=2)
        
        # Output folder
        ttk.Label(settings_grid, text="📁", font=('Segoe UI', 9)).grid(row=1, column=0, sticky=tk.W, padx=2, pady=2)
        self.output_var = tk.StringVar(value=self.output_folder)
        ttk.Entry(settings_grid, textvariable=self.output_var, width=28, state='readonly', font=('Segoe UI', 8)).grid(row=1, column=1, padx=2, pady=2)
        ttk.Button(settings_grid, text="Chọn", command=self.choose_folder, width=6).grid(row=1, column=2, padx=2, pady=2)
        
        # Max concurrent
        ttk.Label(settings_grid, text="⚡", font=('Segoe UI', 9)).grid(row=2, column=0, sticky=tk.W, padx=2)
        self.concurrent_var = tk.IntVar(value=self.max_concurrent)
        concurrent_spin = ttk.Spinbox(settings_grid, from_=1, to=15, textvariable=self.concurrent_var, width=6)
        concurrent_spin.grid(row=2, column=1, sticky=tk.W, padx=2)
        ttk.Label(settings_grid, text="file cùng lúc", font=('Segoe UI', 8)).grid(row=2, column=1, sticky=tk.W, padx=(45, 0))
        
        # Progress
        progress_frame = ttk.LabelFrame(left_frame, text="📊 Tiến trình", padding="4")
        progress_frame.pack(fill=tk.X, pady=2)
        
        self.progress_var = tk.StringVar(value="Sẵn sàng")
        ttk.Label(progress_frame, textvariable=self.progress_var, font=('Segoe UI', 8)).pack()
        
        self.progress_bar = ttk.Progressbar(progress_frame, length=300, mode='determinate')
        self.progress_bar.pack(pady=2)
        
        # ===== RIGHT SIDE: Log Console =====
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        log_frame = ttk.LabelFrame(right_frame, text="📋 Log Console", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)
        
        log_scrollbar = ttk.Scrollbar(log_container)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_container, 
                               width=50,
                               height=30,
                               font=('Consolas', 9),
                               bg='#1e1e1e', 
                               fg='#00ff00',
                               wrap=tk.WORD,
                               yscrollcommand=log_scrollbar.set,
                               state=tk.NORMAL,
                               padx=5,
                               pady=5)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        log_scrollbar.config(command=self.log_text.yview)
        
        # Thêm tags cho log với màu sắc
        self.log_text.tag_config("success", foreground="#00ff00")
        self.log_text.tag_config("error", foreground="#ff4444")
        self.log_text.tag_config("warning", foreground="#ffaa00")
        self.log_text.tag_config("info", foreground="#00aaff")
        
        self.log("✅ Sẵn sàng! Chọn tab để bắt đầu")
        self.log("⚡ Tối ưu: Chunk 4MB | Luồng 5 | SSL tắt")
    
    def setup_single_tab(self):
        """Setup single file download tab"""
        input_frame = ttk.Frame(self.tab_single)
        input_frame.pack(fill=tk.X, pady=2)
        
        # URL input
        url_frame = ttk.LabelFrame(input_frame, text="📌 Link", padding="4")
        url_frame.pack(fill=tk.X, pady=2)
        
        url_row = ttk.Frame(url_frame)
        url_row.pack(fill=tk.X)
        
        self.url_entry = ttk.Entry(url_row, font=('Segoe UI', 9))
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=2, padx=(0, 4))
        
        ttk.Button(url_row, text="🔍 Lấy tên", command=self.auto_get_filename, width=10).pack(side=tk.LEFT)
        
        self.url_entry.bind('<Return>', lambda e: self.auto_get_filename())
        
        # Filename
        name_frame = ttk.LabelFrame(input_frame, text="📝 Tên file", padding="4")
        name_frame.pack(fill=tk.X, pady=2)
        
        filename_row = ttk.Frame(name_frame)
        filename_row.pack(fill=tk.X)
        
        self.filename_var = tk.StringVar(value="video.mp4")
        ttk.Entry(filename_row, textvariable=self.filename_var, font=('Segoe UI', 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        
        ttk.Button(filename_row, text="➕ Thêm", command=self.add_single_file, width=8).pack(side=tk.LEFT)
        
        # Danh sách file
        list_frame = ttk.LabelFrame(self.tab_single, text="📋 Danh sách tải", padding="4")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=2)
        
        # Toolbar
        toolbar = ttk.Frame(list_frame)
        toolbar.pack(fill=tk.X, pady=(0, 2))
        
        self.single_count_var = tk.StringVar(value="0 file")
        ttk.Label(toolbar, textvariable=self.single_count_var, font=('Segoe UI', 8, 'italic')).pack(side=tk.LEFT, padx=4)
        
        ttk.Button(toolbar, text="🗑️ Xóa chọn", command=self.remove_single_files, width=10).pack(side=tk.RIGHT, padx=2)
        ttk.Button(toolbar, text="🗑️ Xóa tất cả", command=self.clear_single_list, width=10).pack(side=tk.RIGHT, padx=2)
        
        # Listbox
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        list_scrollbar = ttk.Scrollbar(list_container)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.single_listbox = tk.Listbox(list_container,
                                         font=('Segoe UI', 9),
                                         selectmode=tk.MULTIPLE,
                                         yscrollcommand=list_scrollbar.set,
                                         height=8)
        self.single_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scrollbar.config(command=self.single_listbox.yview)
        
        # Download button
        btn_frame = ttk.Frame(self.tab_single)
        btn_frame.pack(pady=8)
        
        self.download_btn = tk.Button(btn_frame, text="⬇️ TẢI TẤT CẢ", 
                                     command=self.start_single_download,
                                     font=('Segoe UI', 10, 'bold'),
                                     bg="#1a73e8", fg="white",
                                     padx=30, pady=10,
                                     cursor="hand2",
                                     state=tk.DISABLED)
        self.download_btn.pack()
    
    def setup_folder_tab(self):
        """Setup folder scanning and batch download tab"""
        # Folder URL input
        url_frame = ttk.LabelFrame(self.tab_folder, text="📌 Link Folder", padding="6")
        url_frame.pack(fill=tk.X, pady=2)
        
        url_input_frame = ttk.Frame(url_frame)
        url_input_frame.pack(fill=tk.X)
        
        self.folder_url_entry = ttk.Entry(url_input_frame, font=('Segoe UI', 9))
        self.folder_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        
        ttk.Button(url_input_frame, text="🔍 Quét", 
                  command=self.scan_folder_simple, width=8).pack(side=tk.LEFT)
        
        # File list
        list_frame = ttk.LabelFrame(self.tab_folder, text="📋 Danh sách", padding="4")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=2)
        
        # Toolbar
        toolbar = ttk.Frame(list_frame)
        toolbar.pack(fill=tk.X, pady=(0, 2))
        
        ttk.Button(toolbar, text="☑️ All", command=self.select_all_files, width=7).pack(side=tk.LEFT, padx=1)
        ttk.Button(toolbar, text="☐ None", command=self.deselect_all_files, width=7).pack(side=tk.LEFT, padx=1)
        
        # Checkbox lọc file chưa tải
        self.only_new_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="✨ Chỉ file mới", variable=self.only_new_var, 
                       command=self.apply_new_filter).pack(side=tk.LEFT, padx=4)
        
        ttk.Button(toolbar, text="🗑️", command=self.clear_history, width=3).pack(side=tk.LEFT, padx=1)
        
        self.file_count_var = tk.StringVar(value="0 file")
        ttk.Label(toolbar, textvariable=self.file_count_var, font=('Segoe UI', 8, 'italic')).pack(side=tk.RIGHT, padx=4)
        
        # Treeview
        tree_frame = ttk.Frame(list_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        tree_scroll_y = ttk.Scrollbar(tree_frame)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.file_tree = ttk.Treeview(tree_frame, 
                                      columns=('name', 'progress'),
                                      show='tree headings',
                                      yscrollcommand=tree_scroll_y.set,
                                      xscrollcommand=tree_scroll_x.set,
                                      selectmode='none',
                                      height=10)
        
        style = ttk.Style()
        style.configure("Treeview", rowheight=18, font=('Segoe UI', 8))
        style.configure("Treeview.Heading", font=('Segoe UI', 8, 'bold'))
        
        self.file_tree.heading('#0', text='☑️')
        self.file_tree.heading('name', text='Tên File')
        self.file_tree.heading('progress', text='Tải')
        
        self.file_tree.column('#0', width=25, minwidth=25, stretch=False)
        self.file_tree.column('name', width=200, minwidth=150)
        self.file_tree.column('progress', width=70, minwidth=60)
        
        self.file_tree.pack(fill=tk.BOTH, expand=True)
        
        tree_scroll_y.config(command=self.file_tree.yview)
        tree_scroll_x.config(command=self.file_tree.xview)
        
        self.file_tree.bind('<Button-1>', self.toggle_file_checkbox)
        
        # Download buttons
        btn_frame = ttk.Frame(self.tab_folder)
        btn_frame.pack(pady=8)
        
        # Queue info
        self.queue_info_var = tk.StringVar(value="Queue: 0 file")
        ttk.Label(btn_frame, textvariable=self.queue_info_var, font=('Segoe UI', 8, 'italic')).pack(pady=(0, 4))
        
        btn_row = ttk.Frame(btn_frame)
        btn_row.pack()
        
        self.add_to_queue_btn = tk.Button(btn_row, text="➕ Thêm vào Queue", 
                                         command=self.add_to_queue,
                                         font=('Segoe UI', 9, 'bold'),
                                         bg="#fbbc04", fg="black",
                                         padx=15, pady=8,
                                         cursor="hand2",
                                         state=tk.DISABLED)
        self.add_to_queue_btn.pack(side=tk.LEFT, padx=2)
        
        self.start_queue_btn = tk.Button(btn_row, text="⬇️ Tải Queue", 
                                        command=self.start_queue_download,
                                        font=('Segoe UI', 9, 'bold'),
                                        bg="#34a853", fg="white",
                                        padx=15, pady=8,
                                        cursor="hand2",
                                        state=tk.DISABLED)
        self.start_queue_btn.pack(side=tk.LEFT, padx=2)
        
        self.clear_queue_btn = tk.Button(btn_row, text="🗑️ Xóa Queue", 
                                        command=self.clear_queue,
                                        font=('Segoe UI', 9),
                                        bg="#ea4335", fg="white",
                                        padx=10, pady=8,
                                        cursor="hand2",
                                        state=tk.DISABLED)
        self.clear_queue_btn.pack(side=tk.LEFT, padx=2)
    
    def toggle_file_checkbox(self, event):
        """Toggle checkbox when clicking on tree item"""
        region = self.file_tree.identify_region(event.x, event.y)
        if region == "tree":
            item = self.file_tree.identify_row(event.y)
            if item:
                current_tags = self.file_tree.item(item, 'tags')
                if 'checked' in current_tags:
                    self.file_tree.item(item, tags=('unchecked',), text='☐')
                else:
                    self.file_tree.item(item, tags=('checked',), text='☑️')
                
                self.update_file_count()
    
    def update_file_count(self):
        """Update count of selected files"""
        count = 0
        for item in self.file_tree.get_children():
            if 'checked' in self.file_tree.item(item, 'tags'):
                count += 1
        
        self.file_count_var.set(f"{count} file")
        
        if count > 0:
            self.add_to_queue_btn.config(state=tk.NORMAL)
        else:
            self.add_to_queue_btn.config(state=tk.DISABLED)
    
    def select_all_files(self):
        """Select all files in the tree"""
        for item in self.file_tree.get_children():
            self.file_tree.item(item, tags=('checked',), text='☑️')
        self.update_file_count()
    
    def deselect_all_files(self):
        """Deselect all files in the tree"""
        for item in self.file_tree.get_children():
            self.file_tree.item(item, tags=('unchecked',), text='☐')
        self.update_file_count()
    
    def apply_new_filter(self):
        """Áp dụng filter chỉ chọn file chưa tải"""
        if self.only_new_var.get():
            # Chỉ select file chưa tải
            for item in self.file_tree.get_children():
                tags = self.file_tree.item(item, 'tags')
                if 'downloaded' not in tags:
                    self.file_tree.item(item, tags=('checked',) + tags, text='☑️')
                else:
                    self.file_tree.item(item, tags=('unchecked',) + tags, text='☐')
        else:
            # Select all
            self.select_all_files()
        self.update_file_count()
    
    def clear_history(self):
        """Xóa lịch sử download"""
        if hasattr(self, 'downloaded_files'):
            confirm = messagebox.askyesno("Xác nhận", 
                                         f"Xóa lịch sử download?")
            if confirm:
                self.downloaded_files = []
                self.log("🗑️ Đã xóa lịch sử download")
                messagebox.showinfo("Hoàn thành", "✅ Đã xóa lịch sử!")
    
    def scan_folder_simple(self):
        """Phương pháp quét folder đơn giản nhưng hiệu quả"""
        folder_url = self.folder_url_entry.get().strip()
        
        if not folder_url:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập link folder!")
            return
        
        self.log("=" * 50)
        self.log("🔍 Đang quét folder (phương pháp đơn giản)...")
        
        # Clear tree
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        # Disable buttons during scan
        self.add_to_queue_btn.config(state=tk.DISABLED)
        self.start_queue_btn.config(state=tk.DISABLED)
        self.clear_queue_btn.config(state=tk.DISABLED)
        
        def scan_thread():
            try:
                folder_id = self.extract_folder_id(folder_url)
                
                if not folder_id:
                    self.log("❌ Không tìm thấy Folder ID trong URL")
                    return
                
                self.log(f"✅ Folder ID: {folder_id}")
                
                # Lấy tên folder chính
                folder_name = self.get_folder_name(folder_id)
                if folder_name:
                    self.log(f"📁 Folder: {folder_name}")

                self.scan_root_folder_name = self.clean_filename(folder_name or f"Folder_{folder_id[:8]}")
                
                # Sử dụng phương pháp nâng cao để quét (tương tự testquet.py)
                files = self.get_files_from_folder(folder_id, folder_path=folder_name or "")
                
                if not files:
                    self.scan_root_folder_name = ""
                    self.log("=" * 50)
                    self.log("⚠️ Không tìm thấy file nào")
                    self.log("💡 Thử cung cấp cookies.txt")
                    messagebox.showinfo("Kết quả", "Không tìm thấy file nào!\n\nHãy thử cung cấp file cookies.txt để truy cập folder private.")
                    return
                
                self.log("=" * 50)
                self.log(f"✅ Tổng: {len(files)} file")
                
                # Thêm vào tree
                added_count = 0
                excluded_count = 0
                
                for file_info in files:
                    if file_info['type'] == 'file':
                        # Clean tên file (bỏ watermark)
                        cleaned_name = self.clean_filename(file_info['display_name'])
                        # Kiểm tra file có bị loại trừ không (so sánh trên tên đã dọn)
                        if self.is_excluded_file(cleaned_name):
                            excluded_count += 1
                            self.log(f"⛔ Bỏ qua: {cleaned_name}")
                            continue

                        file_url = file_info['url']
                        is_downloaded = False
                        
                        icon = '✅' if is_downloaded else '📄'
                        name_display = f"{icon} {cleaned_name}"
                        
                        # Chỉ tự động check file CHƯA tải
                        check_text = '☐' if is_downloaded else '☑️'
                        tags_list = ['unchecked'] if is_downloaded else ['checked']
                        # Store URL, the full path name (with folders), extension and type so add_to_queue can retrieve them
                        tags_list.extend([file_info['url'], file_info['name']])
                        # include ext and type as tags for later queue building
                        ext_tag = file_info.get('ext') or file_info.get('extension') or ''
                        tags_list.append(f"ext::{ext_tag}")
                        tags_list.append(f"type::{file_info.get('file_type','')}")
                        if file_info.get('scan_root'):
                            tags_list.append(f"scanroot::{file_info['scan_root']}")
                        if is_downloaded:
                            tags_list.append('downloaded')
                        
                        # Hiển thị progress
                        progress_text = '✅ 100%' if is_downloaded else '⏳ 0%'
                        
                        item_id = self.file_tree.insert('', tk.END, 
                                            text=check_text,
                                            values=(name_display, progress_text),
                                            tags=tuple(tags_list))
                        
                        # Lưu map URL -> item ID để update progress sau
                        self.file_tree_items[file_info['url']] = item_id
                        added_count += 1
                
                self.log(f"📄 Đã thêm {added_count} files vào danh sách")
                
                if excluded_count > 0:
                    self.log(f"⛔ Đã bỏ qua {excluded_count} file quảng cáo")
                
                self.log("=" * 50)
                self.log("✅ HOÀN THÀNH QUÉT!")
                self.log("👉 File đã được tự động chọn")
                
                self.update_file_count()
                
                # Hiển thị thông báo
                msg = f"✅ Đã tìm thấy {added_count} files!"
                if excluded_count > 0:
                    msg += f"\n⛔ Đã bỏ qua {excluded_count} file quảng cáo"
                msg += f"\n\n👉 Nhấn '➕ Thêm vào Queue' để chuẩn bị tải"
                
                messagebox.showinfo("Quét xong!", msg)
                self.scan_root_folder_name = ""
                
            except Exception as e:
                self.log(f"❌ Lỗi quét folder: {str(e)}")
                import traceback
                self.log(traceback.format_exc())
                self.scan_root_folder_name = ""
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def simple_scan_drive_folder(self, folder_id, parent_path="", depth=0, max_depth=3):
        """Phương pháp quét folder đơn giản nhưng hiệu quả"""
        files = []
        
        try:
            if depth > max_depth:
                self.log(f"⚠️ Đã đạt độ sâu tối đa ({max_depth}), dừng quét")
                return files
            
            session = self.get_session()
            
            # Truy cập trang folder
            folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
            
            if parent_path == "":
                self.log(f"📂 Đang quét folder: {folder_id}...")
            else:
                self.log(f"📁 [Depth {depth}] Quét: {parent_path}")
            
            response = session.get(folder_url, timeout=30)
            html = response.text
            
            # Lưu HTML để debug (toàn bộ, giúp pattern match sâu trong JS)
            try:
                with open('debug_folder.html', 'w', encoding='utf-8') as f:
                    f.write(html)
            except:
                pass
            
            # PHƯƠNG PHÁP ĐƠN GIẢN: Tìm tất cả các cặp ["id", "tên file"] trong HTML
            found_items = []
            
            # Pattern 1: Tìm các mảng ["id", "tên file", ...]
            pattern1 = r'\["([a-zA-Z0-9_-]{25,45})","([^"]+)",([^\]]+)\]'
            matches1 = re.findall(pattern1, html)
            
            self.log(f"🔍 Pattern 1 tìm thấy: {len(matches1)} items")
            
            for match in matches1:
                item_id = match[0]
                item_name = match[1]
                other_data = match[2]
                
                # Kiểm tra xem có phải folder không
                if '"application/vnd.google-apps.folder"' in other_data:
                    # Đây là folder
                    found_items.append({
                        'type': 'folder',
                        'id': item_id,
                        'name': item_name,
                        'data': other_data
                    })
                else:
                    # Đây là file
                    found_items.append({
                        'type': 'file',
                        'id': item_id,
                        'name': item_name,
                        'data': other_data
                    })
            
            # Pattern 2: Tìm các chuỗi dài hơn
            pattern2 = r'"([a-zA-Z0-9_-]{25,45})","([^"]{3,200})","([^"]+)","([^"]+)","([^"]+)","([^"]+)"'
            matches2 = re.findall(pattern2, html)
            
            self.log(f"🔍 Pattern 2 tìm thấy: {len(matches2)} items")
            
            for match in matches2:
                item_id = match[0]
                item_name = match[1]
                mime_type = match[2]
                
                if 'folder' in mime_type.lower():
                    # Đây là folder
                    found_items.append({
                        'type': 'folder',
                        'id': item_id,
                        'name': item_name,
                        'mime_type': mime_type
                    })
                else:
                    # Đây là file
                    found_items.append({
                        'type': 'file',
                        'id': item_id,
                        'name': item_name,
                        'mime_type': mime_type
                    })
            
            # Xử lý kết quả
            file_count = 0
            folder_count = 0
            
            for item in found_items:
                if item['type'] == 'file':
                    file_count += 1
                    
                    # Tạo thông tin file
                    file_name = item['name']
                    file_id = item['id']
                    
                    # Xác định extension
                    base_name, ext = os.path.splitext(file_name)
                    if not ext:
                        ext = ""

                    should_skip, skip_reason = self.should_skip_file(file_name)
                    if should_skip:
                        self.log(f"⛔ Bỏ qua: {file_name[:120]} ({skip_reason})")
                        continue
                    
                    file_type = 'file'
                    if ext.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v']:
                        file_type = 'video'
                    elif ext.lower() in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a']:
                        file_type = 'audio'
                    elif ext.lower() in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.zip', '.rar', '.7z']:
                        file_type = 'document'
                    
                    # Tạo tên file với path
                    display_name = file_name
                    if parent_path:
                        clean_name = self.clean_filename(file_name)
                        clean_path = parent_path.replace('\\', '/')
                        file_name_with_path = f"{clean_path}/{clean_name}"
                    else:
                        file_name_with_path = self.clean_filename(file_name)
                    
                    # Lọc các entry không phải file người dùng (URL nội bộ, blob, metadata)
                    name_lower = file_name.lower()
                    internal_skip = None
                    if name_lower.startswith('http') or name_lower.startswith('https') or name_lower.startswith('https_/'):
                        internal_skip = 'URL resource'
                    if any(k in name_lower for k in ['blobcomments', 'drivemetadata', 'driveweb', 'usercontent', 'blob']):
                        internal_skip = 'internal blob/metadata'
                    if internal_skip:
                        self.log(f"⛔ Bỏ qua (không phải file): {file_name[:80]} ({internal_skip})")
                    else:
                        files.append({
                        'id': file_id,
                        'name': file_name_with_path,  # Tên với full path
                        'display_name': file_name,     # Tên gốc
                        'extension': ext,
                        'file_type': file_type,
                        'size': 'N/A',
                        'type': 'file',
                        'url': f"https://drive.google.com/file/d/{file_id}/view"
                        })
                    
                elif item['type'] == 'folder':
                    folder_count += 1
            
            self.log(f"📊 Phân loại: {file_count} file, {folder_count} folder")
            
            # QUÉT ĐỆ QUY CÁC FOLDER CON
            if folder_count > 0:
                self.log("")
                self.log("=" * 50)
                self.log(f"🔽 BẮT ĐẦU QUÉT ĐỆ QUY {folder_count} SUBFOLDER...")
                self.log("=" * 50)
                
                subfolder_files_count = 0
                
                for item in found_items:
                    if item['type'] == 'folder':
                        subfolder_id = item['id']
                        subfolder_name = item['name']
                        
                        # Tạo path cho subfolder
                        clean_subfolder_name = self.clean_filename(subfolder_name)
                        new_path = f"{parent_path}/{clean_subfolder_name}" if parent_path else clean_subfolder_name
                        
                        self.log(f"🔽 Quét subfolder: {subfolder_name}")
                        
                        try:
                            # Quét đệ quy subfolder
                            subfolder_files = self.simple_scan_drive_folder(
                                folder_id=subfolder_id,
                                parent_path=new_path,
                                depth=depth + 1,
                                max_depth=max_depth
                            )
                            
                            # Thêm files từ subfolder vào danh sách
                            if subfolder_files:
                                files.extend(subfolder_files)
                                subfolder_files_count += len(subfolder_files)
                                self.log(f"   ✅ Tìm thấy {len(subfolder_files)} file")
                            
                        except Exception as e:
                            self.log(f"   ❌ Lỗi quét subfolder: {str(e)}")
                
                if subfolder_files_count > 0:
                    self.log(f"✅ Tổng từ subfolders: {subfolder_files_count} file")
            
            self.log(f"📊 Tổng cộng: {len(files)} file")
            # Fallback: nếu không tìm thấy file bởi các pattern trên, dò trực tiếp các /file/d/<id>/view
            if len(files) == 0:
                try:
                    ids = re.findall(r'/file/d/([A-Za-z0-9_-]{10,})/view', html)
                    # preserve order and unique
                    ids = list(dict.fromkeys(ids))
                    if ids:
                        self.log(f"🔎 Fallback parser tìm thấy {len(ids)} file id via /file/d/ pattern")
                        for fid in ids:
                            should_skip, skip_reason = self.should_skip_file(fid)
                            if should_skip:
                                self.log(f"⛔ Bỏ qua: {fid[:120]} ({skip_reason})")
                                continue
                            files.append({
                                'id': fid,
                                'name': self.clean_filename(fid),
                                'display_name': fid,
                                'extension': '',
                                'file_type': 'other',
                                'size': 'N/A',
                                'type': 'file',
                                'url': f"https://drive.google.com/file/d/{fid}/view"
                            })
                except Exception as e:
                    self.log(f"⚠️ Fallback parser lỗi: {str(e)}")

            self.log(f"📊 Tổng cộng: {len(files)} file")
            return files
            
        except Exception as e:
            self.log(f"❌ Lỗi quét folder: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            return []
    
    def extract_folder_id(self, url):
        """Extract folder ID from Google Drive URL"""
        patterns = [
            r'/folders/([a-zA-Z0-9_-]+)',
            r'id=([a-zA-Z0-9_-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None

    def get_file_type(self, filename, mime_type=None):
        """Xác định loại file từ tên trả về (file_type, extension)"""
        base_name, ext = os.path.splitext(filename)
        ext = ext.lower()

        mime_to_ext = {
            'application/pdf': ('.pdf', 'document'),
            'application/msword': ('.doc', 'document'),
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ('.docx', 'document'),
            'application/vnd.ms-excel': ('.xls', 'document'),
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ('.xlsx', 'document'),
            'application/vnd.ms-powerpoint': ('.ppt', 'document'),
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': ('.pptx', 'document'),
            'text/plain': ('.txt', 'document'),
            'application/zip': ('.zip', 'document'),
            'application/x-7z-compressed': ('.7z', 'document'),
            'application/x-rar-compressed': ('.rar', 'document'),
            'video/mp4': ('.mp4', 'video'),
            'video/x-matroska': ('.mkv', 'video'),
            'video/x-msvideo': ('.avi', 'video'),
            'video/quicktime': ('.mov', 'video'),
            'video/webm': ('.webm', 'video'),
            'audio/mpeg': ('.mp3', 'audio'),
            'audio/wav': ('.wav', 'audio'),
            'audio/flac': ('.flac', 'audio'),
            'audio/mp4': ('.m4a', 'audio'),
            'image/jpeg': ('.jpg', 'image'),
            'image/png': ('.png', 'image'),
            'image/gif': ('.gif', 'image'),
        }

        # Nếu không có extension, ưu tiên suy theo MIME type của Drive
        if not ext:
            if mime_type and mime_type in mime_to_ext:
                inferred_ext, inferred_type = mime_to_ext[mime_type]
                return inferred_type, inferred_ext

            # fallback an toàn hơn: giữ file nhưng đánh dấu kiểu chưa rõ
            return 'other', ''

        video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v']
        audio_exts = ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a']
        doc_exts = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.zip', '.rar', '.7z']

        if ext in video_exts:
            return 'video', ext
        if ext in audio_exts:
            return 'audio', ext
        if ext in doc_exts:
            return 'document', ext

        return 'other', ext

    def normalize_name_for_match(self, name):
        """Normalize a filename/folder name for stable exact matching."""
        if not name:
            return ""

        try:
            import unicodedata
            normalized = unicodedata.normalize('NFD', name)
            normalized = ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')
        except Exception:
            normalized = name

        normalized = normalized.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = normalized.replace('–', '-').replace('—', '-')
        return normalized

    def should_skip_file(self, filename):
        """Skip only exact junk entries and obvious internal placeholders."""
        if not filename:
            return True, "empty name"

        base_name = os.path.basename(filename)
        normalized_full = self.normalize_name_for_match(filename)
        normalized_base = self.normalize_name_for_match(base_name)
        name_no_ext, ext = os.path.splitext(base_name)
        normalized_no_ext = self.normalize_name_for_match(name_no_ext)

        # Only these exact ad/placeholder names should be excluded.
        exact_excluded_names = {
            self.normalize_name_for_match(x)
            for x in self.excluded_filenames
        }

        if normalized_base in exact_excluded_names:
            return True, 'exact excluded name'

        # Drive often creates duplicate copies with names like "Bản sao của ...".
        # Skip those automatically so they do not reappear on every scan.
        if normalized_base.startswith('ban sao cua ') or normalized_base.startswith('copy of '):
            return True, 'duplicate copy name'

        # Keep files without extensions; they can still be valid Drive files.
        # Only filter obvious internal content, not user-uploaded filenames.
        if ext == '':
            return False, ''

        return False, ''
    
    def get_session(self):
        """Tạo session với cookies"""
        if self._session is not None and self._session_cookie_path == self.cookies_file:
            return self._session

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        
        if self.cookies_file and os.path.exists(self.cookies_file):
            # Try loading cookies using a robust loader that supports multiple formats
            try:
                if self.load_cookies_into_session(session, self.cookies_file):
                    if not hasattr(self, '_cookies_logged'):
                        self._cookies_logged = True
                        self.log(f"🍪 Đã load {len(session.cookies)} cookies từ file")
                else:
                    self.log("⚠️ Không load được cookies từ file (format không hỗ trợ)")
            except Exception as e:
                self.log(f"⚠️ Lỗi load cookies: {str(e)}")
        
        self._session = session
        self._session_cookie_path = self.cookies_file
        return session

    def load_cookies_into_session(self, session, path):
        """Try loading cookies from several common formats into requests session."""
        self.log("🍪 Đang load cookies...")
        # 1) Try Mozilla/Netscape format
        try:
            cj = MozillaCookieJar(path)
            cj.load(ignore_discard=True, ignore_expires=True)
            session.cookies = cj
            self.log(f"✅ Đã load {len(session.cookies)} cookies (mozilla format)")
            return True
        except Exception as e:
            self.log(f"⚠️ Không load được cookies (mozilla): {str(e)}")

        # 2) Try JSON export
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = f.read().strip()
            if data.startswith('{') or data.startswith('['):
                parsed = json.loads(data)
                jar = requests.cookies.RequestsCookieJar()
                if isinstance(parsed, dict):
                    if 'cookies' in parsed and isinstance(parsed['cookies'], list):
                        for ck in parsed['cookies']:
                            name = ck.get('name') or ck.get('Name') or ck.get('key')
                            value = ck.get('value') or ck.get('Value') or ck.get('val')
                            domain = ck.get('domain') or ck.get('Domain') or '.google.com'
                            path_val = ck.get('path') or ck.get('Path') or '/'
                            if name:
                                jar.set(name, value, domain=domain, path=path_val)
                    else:
                        for k, v in parsed.items():
                            if isinstance(v, (str, int, float)):
                                jar.set(k, str(v), domain='.google.com', path='/')
                elif isinstance(parsed, list):
                    for ck in parsed:
                        if isinstance(ck, dict):
                            name = ck.get('name') or ck.get('Name') or ck.get('key')
                            value = ck.get('value') or ck.get('Value') or ck.get('val')
                            domain = ck.get('domain') or ck.get('Domain') or '.google.com'
                            path_val = ck.get('path') or ck.get('Path') or '/'
                            if name:
                                jar.set(name, value, domain=domain, path=path_val)

                if len(jar) > 0:
                    session.cookies = jar
                    self.log(f"✅ Đã load {len(session.cookies)} cookies (json format)")
                    return True
        except Exception as e:
            self.log(f"⚠️ JSON cookies parse failed: {str(e)}")

        # 3) Try simple text parsing (Netscape tab-separated)
        try:
            jar = requests.cookies.RequestsCookieJar()
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '\t' in line:
                        parts = line.split('\t')
                        if len(parts) >= 7:
                            domain = parts[0]
                            path_val = parts[2]
                            name = parts[-2]
                            value = parts[-1]
                            jar.set(name, value, domain=domain, path=path_val)
                            continue
                    if '=' in line:
                        name, value = line.split('=', 1)
                        jar.set(name.strip(), value.strip(), domain='.google.com', path='/')

            if len(jar) > 0:
                session.cookies = jar
                self.log(f"✅ Đã load {len(session.cookies)} cookies (simple format)")
                return True
        except Exception as e:
            self.log(f"⚠️ Plain parse failed: {str(e)}")

        return False
    
    def get_folder_name(self, folder_id):
        """Lấy tên folder từ ID"""
        try:
            session = self.get_session()
            folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
            response = session.get(folder_url, timeout=10)
            html = response.text
            
            # Tìm tên folder trong title tag
            title_match = re.search(r'<title>(.+?)\s*-\s*Google Drive</title>', html)
            if title_match:
                name = title_match.group(1).strip()
                if name and name != "Google Drive":
                    return name
            
            return None
        except:
            return None

    def get_files_from_folder(self, folder_id, folder_path="", depth=0, max_depth=5, visited=None):
        """Lấy danh sách file từ folder Google Drive (có thể đệ quy).
        Ported from testquet.py with small compatibility adjustments.
        Returns a list of dicts: {'id','name','type','ext','url'}."""
        files = []
        seen_file_ids = set()

        if visited is None:
            visited = set()

        if folder_id in visited:
            self.log(f"⚠️ Bỏ qua folder đã quét: {folder_id[:12]}...")
            return files

        visited.add(folder_id)

        try:
            if depth > max_depth:
                self.log(f"⚠️ Đã đạt độ sâu tối đa ({max_depth}), dừng quét")
                return files

            session = self.get_session()
            folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
            self.log(f"🌐 Đang truy cập: {folder_url}")
            response = session.get(folder_url, timeout=30)

            if response.status_code != 200:
                self.log(f"❌ HTTP {response.status_code} - {response.reason}")
                return files

            html = response.text
            self.log(f"✓ Đã tải HTML ({len(html)} bytes)")

            if "accounts.google.com" in response.url:
                self.log("❌ Bị redirect đến trang login - Cookies không hợp lệ hoặc đã hết hạn")
                return files

            if "Request access" in html or "You need permission" in html:
                self.log("❌ Folder private - Không có quyền truy cập")
                return files

            # Save debug HTML
            try:
                debug_file = f"folder_debug_{folder_id[:12]}.html"
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(html)
                self.log(f"💾 Đã lưu HTML vào {debug_file}")
            except:
                pass

            found_files = {}
            found_subfolders = {}

            # Try to extract ID + mime entries encoded in HTML (pattern seen in Drive)
            id_mime_pattern = r'\[null,&quot;([a-zA-Z0-9_-]{33})&quot;\][^\[]{0,300}?&quot;(application/vnd\.google-apps\.[^&]+|[a-z]+/[a-z0-9+.-]+)&quot;'

            for match in re.finditer(id_mime_pattern, html, re.DOTALL):
                item_id = match.group(1)
                mime_type = match.group(2)

                if item_id == folder_id:
                    continue
                if item_id in found_files or item_id in found_subfolders:
                    continue

                context_start = match.end()
                context = html[context_start:context_start + 2000]

                name_pattern = r'\[\[&quot;([^&]+?)&quot;,null,true\]\]'
                name_match = re.search(name_pattern, context)

                if name_match:
                    item_name = name_match.group(1)
                    item_name = item_name.replace('\\u0026', '&').replace('&amp;', '&')
                else:
                    fallback_pattern = r'&quot;([^&]{3,80}?)&quot;'
                    skip_values = {'vi', 'en', 'true', 'false', 'Modified', 'Size not available', 'Shared folder', 'http', 'https', '—', 'Chia sẻ', 'Tải xuống'}
                    item_name = None
                    for fb_match in re.finditer(fallback_pattern, context):
                        candidate = fb_match.group(1)
                        if not any(skip in candidate for skip in skip_values) and len(candidate) >= 3:
                            item_name = candidate.replace('\\u0026', '&').replace('&amp;', '&')
                            break
                    if not item_name:
                        item_name = f"Unknown_{item_id[:8]}"

                if not item_name:
                    continue

                if 'folder' in mime_type:
                    clean_name = self.clean_filename(item_name)
                    found_subfolders[item_id] = clean_name
                    self.log(f"  📁 {clean_name} (ID: {item_id[:8]}...)")
                else:
                    if item_id in seen_file_ids:
                        continue
                    # test.py's get_file_type returns (base, type, ext)
                    file_type, ext = self.get_file_type(item_name, mime_type)
                    clean_name = self.clean_filename(item_name)
                    display_name = f"{folder_path}/{clean_name}" if folder_path else clean_name
                    # Normalize file dict to include display_name and mark as 'file' for compatibility
                    found_files[item_id] = {
                        'id': item_id,
                        'name': display_name,
                        'display_name': clean_name,
                        'type': 'file',
                        'file_type': file_type,
                        'ext': ext,
                        'scan_root': self.scan_root_folder_name,
                        'url': f"https://drive.google.com/file/d/{item_id}/view"
                    }
                    seen_file_ids.add(item_id)
                    self.log(f"  ✓ {clean_name} (ID: {item_id[:8]}...)")

            files = list(found_files.values())
            self.log(f"📊 {len(files)} file, {len(found_subfolders)} subfolder trong folder này")

            # Fallback: nếu không tìm thấy file bằng pattern trên, dò các /file/d/<id>/view (escaped hoặc không)
            if len(files) == 0:
                try:
                    # tìm cả dạng escaped "https:\/\/drive.google.com\/file\/d\/...\/view" và không escaped
                    ids_escaped = re.findall(r'https?:\\/\\/drive\.google\.com\\/file\\/d\\/([A-Za-z0-9_-]{10,})\\/view', html)
                    ids_plain = re.findall(r'/file/d/([A-Za-z0-9_-]{10,})/view', html)
                    ids = list(dict.fromkeys(ids_escaped + ids_plain))
                    # ALSO try to detect subfolder IDs (escaped and plain)
                    folder_ids_escaped = re.findall(r'https?:\\/\\/drive\.google\.com\\/drive\\/folders\\/([A-Za-z0-9_-]{10,})', html)
                    folder_ids_plain = re.findall(r'/drive/folders/([A-Za-z0-9_-]{10,})', html)
                    folder_ids = list(dict.fromkeys(folder_ids_escaped + folder_ids_plain))

                    if folder_ids:
                        self.log(f"🔎 Fallback parser tìm thấy {len(folder_ids)} subfolder id via /drive/folders/ pattern")
                        # limit recursion depth and number of folders to check
                        max_folders = 20
                        for fid in folder_ids[:max_folders]:
                            if fid in visited:
                                continue
                            # attempt to get folder name
                            fname = self.get_folder_name(fid) or f"Folder_{fid[:8]}"
                            self.log(f"  ↳ Quét subfolder fallback: {fname} (ID: {fid})")
                            if depth + 1 <= max_depth:
                                subfiles = self.get_files_from_folder(fid, folder_path=f"{folder_path}/{fname}" if folder_path else fname, depth=depth+1, max_depth=max_depth, visited=visited)
                                if subfiles:
                                    files.extend(subfiles)
                                    self.log(f"    ✓ Tìm thấy {len(subfiles)} file trong subfolder {fname}")

                    if ids:
                        self.log(f"🔎 Fallback parser tìm thấy {len(ids)} file id via /file/d/ pattern")
                        # limit to avoid excessive requests
                        max_check = 200
                        for fid in ids[:max_check]:
                            info = self.get_file_info(fid)
                            if info:
                                if info['id'] in seen_file_ids:
                                    continue
                                # ensure scan_root is present
                                info['scan_root'] = self.scan_root_folder_name
                                # clean and build a name that preserves folder_path
                                display_raw = info.get('display_name') or info.get('name') or fid
                                display_clean = self.clean_filename(display_raw)
                                info['display_name'] = display_clean
                                info['name'] = f"{folder_path}/{display_clean}" if folder_path else display_clean

                                should_skip, skip_reason = self.should_skip_file(display_clean)
                                if should_skip:
                                    self.log(f"⛔ Bỏ qua: {display_clean[:120]} ({skip_reason})")
                                    continue

                                files.append(info)
                                seen_file_ids.add(info['id'])
                                self.log(f"  ✓ Lấy thông tin: {display_clean[:80]}")
                            else:
                                # fallback minimal entry
                                display_clean = self.clean_filename(fid)
                                full_name = f"{folder_path}/{display_clean}" if folder_path else display_clean
                                should_skip, skip_reason = self.should_skip_file(display_clean)
                                if should_skip:
                                    self.log(f"⛔ Bỏ qua: {display_clean[:120]} ({skip_reason})")
                                    continue
                                files.append({
                                    'id': fid,
                                    'name': full_name,
                                    'display_name': display_clean,
                                    'type': 'file',
                                    'file_type': 'other',
                                    'ext': '',
                                    'scan_root': self.scan_root_folder_name,
                                    'url': f"https://drive.google.com/file/d/{fid}/view"
                                })
                                seen_file_ids.add(fid)
                                self.log(f"  ⚠️ Không lấy được tên, thêm ID: {display_clean}")
                        self.log(f"🔎 Fallback added {len(files)} files")
                except Exception as e:
                    self.log(f"⚠️ Fallback parser lỗi: {str(e)}")

            do_recursive = True if not hasattr(self, 'recursive_var') else self.recursive_var.get()
            if do_recursive and found_subfolders:
                self.log(f"📂 Quét đệ quy {len(found_subfolders)} subfolder (depth={depth})...")
                for idx, (subfolder_id, subfolder_name) in enumerate(found_subfolders.items(), 1):
                    if subfolder_name:
                        new_path = f"{folder_path}/{subfolder_name}" if folder_path else subfolder_name
                        self.log(f"  [{idx}/{len(found_subfolders)}] ↳ Quét: {new_path}")
                    else:
                        new_path = f"{folder_path}/Folder_{subfolder_id[:8]}" if folder_path else f"Folder_{subfolder_id[:8]}"
                        self.log(f"  [{idx}/{len(found_subfolders)}] ↳ Quét: {new_path} (ID: {subfolder_id})")

                    subfolder_files = self.get_files_from_folder(subfolder_id, new_path, depth + 1, max_depth, visited)
                    if subfolder_files:
                        self.log(f"    ✓ Tìm thấy {len(subfolder_files)} file trong subfolder")
                        files.extend(subfolder_files)
                    else:
                        self.log(f"    ⚠️ Không có file trong subfolder này")
                    if self.scan_delay > 0:
                        time.sleep(self.scan_delay)

            return files

        except Exception as e:
            self.log(f"❌ Lỗi quét folder: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_file_info(self, file_id):
        """Lấy thông tin 1 file từ ID"""
        try:
            session = self.get_session()
            url = f"https://drive.google.com/file/d/{file_id}/view"
            response = session.get(url, timeout=10)
            html = response.text
            
            name = None
            
            # Pattern 1: <title>TenFile - Google Drive</title>
            title_match = re.search(r'<title>(.+?)\s*-\s*Google Drive</title>', html)
            if title_match:
                name = title_match.group(1).strip()
            
            if name and name != "Google Drive" and len(name) > 1:
                base_name, ext = os.path.splitext(name)
                if not ext:
                    ext = ""
                
                file_type = 'file'
                if ext.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v']:
                    file_type = 'video'
                elif ext.lower() in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a']:
                    file_type = 'audio'
                
                return {
                    'id': file_id,
                    'name': os.path.splitext(name)[0],
                    'display_name': name,
                    'extension': ext,
                    'file_type': file_type,
                    'size': 'N/A',
                    'type': 'file',
                    'url': url
                }
            return None
        except Exception as e:
            return None
    
    def format_size(self, size_bytes):
        """Format file size to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
    
    def clean_filename(self, name):
        """Loại bỏ các đoạn quảng cáo/watermark khỏi tên file"""
        if not name:
            return name
        
        # Các pattern cần loại bỏ
        patterns_to_remove = [
            r'\s*\(website khoahocgiahoi\.com zalo \d+\)',
            r'\s*\([^)]*khoahocgiahoi\.com[^)]*\)',
            r'\s*\([^)]*zalo\s*\d+[^)]*\)',
            r'\s*\[khoahocgiahoi\.com[^\]]*\]',
            r'\s*khoahocgiahoi\.com',
            r'\s*-\s*khoahocgiahoi\.com',
            r'\s*_\s*khoahocgiahoi\.com',
            r'\s*\(\s*zalo\s*:?\s*\d{9,11}\s*\)',
            r'\s*zalo\s*:?\s*\d{9,11}',
            r'\s*\([^)]*(?:facebook|fb|telegram|tele)\.com[^)]*\)',
            r'\s*\(khoahocgiahoi\.com\s*zalo\s*\d{6,}\)\s*$',
        ]
        
        cleaned = name
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Xóa khoảng trắng thừa
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Thay thế các ký tự không hợp lệ trong Windows (giữ / cho folder structure)
        invalid_chars = r'[<>:"|?*]'
        cleaned = re.sub(invalid_chars, '_', cleaned)
        
        # Xử lý từng phần của path (tách bởi /)
        parts = cleaned.split('/')
        cleaned_parts = []
        
        for part in parts:
            part = part.strip('. ')
            if len(part) > 100:
                part = part[:97] + '...'
            if part:
                cleaned_parts.append(part)
        
        cleaned = '/'.join(cleaned_parts)
        cleaned = re.sub(r'^[-_\s]+|[-_\s]+$', '', cleaned)
        cleaned = re.sub(r'\s+\.(?=[A-Za-z0-9]{1,5}$)', '.', cleaned)
        
        return cleaned if cleaned else name

    def ensure_file_extension(self, filename, file_info=None):
        """Append a file extension when the name does not already have one."""
        if not filename:
            return filename

        base_name = os.path.basename(filename)
        root_name, current_ext = os.path.splitext(base_name)
        if current_ext:
            return filename

        preferred_ext = ""
        if file_info:
            preferred_ext = (
                file_info.get('ext') or
                file_info.get('extension') or
                file_info.get('file_ext') or
                ""
            )

        if not preferred_ext:
            file_type = (file_info or {}).get('file_type', '')
            default_ext_map = {
                'video': '.mp4',
                'audio': '.mp3',
                'document': '.pdf',
                'image': '.jpg',
            }
            preferred_ext = default_ext_map.get(file_type, '.mp4')

        if preferred_ext and not preferred_ext.startswith('.'):
            preferred_ext = f'.{preferred_ext}'

        if not preferred_ext:
            return filename

        return f"{filename}{preferred_ext}"

    def build_output_path(self, file_info):
        """Build a nested output path under the chosen folder and ensure a file extension."""
        raw_name = file_info.get('name') or file_info.get('display_name') or file_info.get('filename') or ''
        raw_name = self.ensure_file_extension(raw_name, file_info)

        parts = raw_name.replace('\\', '/').split('/')
        parts = [part for part in parts if part]
        if not parts:
            return self.output_folder

        scan_root = (file_info.get('scan_root') or getattr(self, 'scan_root_folder_name', '')).strip()
        if scan_root:
            safe_scan_root = re.sub(r'[<>:\"|?*]', '_', scan_root).strip()
            if safe_scan_root:
                first_part = re.sub(r'[<>:\"|?*]', '_', parts[0]).strip()
                if self.normalize_name_for_match(first_part) != self.normalize_name_for_match(safe_scan_root):
                    parts = [safe_scan_root] + parts

        folder_parts = parts[:-1]
        file_name = parts[-1]

        current_path = self.output_folder
        for folder in folder_parts:
            safe_folder = re.sub(r'[<>:\"|?*]', '_', folder).strip()
            if safe_folder:
                current_path = os.path.join(current_path, safe_folder)
                os.makedirs(current_path, exist_ok=True)

        safe_filename = re.sub(r'[<>:\"|?*]', '_', file_name).strip()
        return os.path.join(current_path, safe_filename)
    
    def is_excluded_file(self, filename):
        """Kiểm tra xem file có nằm trong danh sách loại trừ không"""
        try:
            import unicodedata
            
            def normalize(s):
                nfd = unicodedata.normalize('NFD', s)
                no_accent = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
                return re.sub(r'\s+', ' ', no_accent).strip().lower()
            
            name_without_ext = os.path.splitext(filename)[0]
            basename = os.path.basename(name_without_ext)
            
            normalized_full = normalize(filename)
            normalized_name = normalize(name_without_ext)
            normalized_base = normalize(basename)

            exact_excluded = {
                normalize(os.path.splitext(excluded)[0])
                for excluded in self.excluded_filenames
            }

            if normalized_full in exact_excluded or normalized_name in exact_excluded or normalized_base in exact_excluded:
                return True
            
            return False
        except:
            return False
    
    def add_to_queue(self):
        """Add selected files to download queue"""
        selected_files = []
        for item in self.file_tree.get_children():
            if 'checked' in self.file_tree.item(item, 'tags'):
                values = self.file_tree.item(item, 'values')
                tags = self.file_tree.item(item, 'tags')
                
                url = None
                full_name = None
                scan_root = ""
                
                ext_val = ''
                type_val = ''
                for tag in tags:
                    if tag.startswith('http'):
                        url = tag
                    elif tag.startswith('scanroot::'):
                        scan_root = tag.split('scanroot::', 1)[1].strip()
                    elif tag.startswith('ext::'):
                        ext_val = tag.split('ext::', 1)[1]
                    elif tag.startswith('type::'):
                        type_val = tag.split('type::', 1)[1]
                    elif '/' in tag or '.' in tag:
                        full_name = tag
                
                if url and full_name:
                    selected_files.append({
                        'name': full_name,
                        'url': url,
                        'scan_root': scan_root,
                        'ext': locals().get('ext_val',''),
                        'file_type': locals().get('type_val','')
                    })
        
        if not selected_files:
            messagebox.showwarning("Không có file", "Vui lòng chọn ít nhất 1 file!")
            return
        
        # Thêm vào pending queue
        added = 0
        for file_info in selected_files:
            # Normalize name: remove watermark and ensure extension
            name_raw = file_info.get('name') or ''
            cleaned = self.clean_filename(name_raw)
            # attach ext/type if provided
            if file_info.get('ext'):
                cleaned = self.ensure_file_extension(cleaned, {'ext': file_info.get('ext'), 'file_type': file_info.get('file_type')})
            else:
                cleaned = self.ensure_file_extension(cleaned, {'file_type': file_info.get('file_type')})

            file_info['name'] = cleaned

            if not any(f['url'] == file_info['url'] for f in self.pending_files):
                self.pending_files.append(file_info)
                added += 1
        
        self.log(f"➕ Đã thêm {added} file vào Queue (bỏ qua {len(selected_files) - added} file trùng)")
        self.update_queue_info()
        
        # Deselect all sau khi thêm
        self.deselect_all_files()
        
        messagebox.showinfo("Đã thêm", 
                          f"✅ Đã thêm {added} file vào Queue!\n"
                          f"Tổng Queue: {len(self.pending_files)} file\n\n"
                          f"💡 Có thể quét thêm folder khác rồi nhấn 'Thêm vào Queue'\n"
                          f"Khi sẵn sàng, nhấn '⬇️ Tải Queue' để bắt đầu tải")
    
    def update_file_progress(self, url, percent):
        """Cập nhật tiến độ tải file trên tree view"""
        try:
            if url in self.file_tree_items:
                item_id = self.file_tree_items[url]
                if percent >= 100:
                    progress_text = '✅ 100%'
                else:
                    progress_text = f'⬇️ {percent:.0f}%'
                
                current_values = list(self.file_tree.item(item_id, 'values'))
                if len(current_values) >= 2:
                    current_values[1] = progress_text
                    self.file_tree.item(item_id, values=current_values)
        except:
            pass
    
    def update_queue_info(self):
        """Update queue information display"""
        count = len(self.pending_files)
        self.queue_info_var.set(f"Queue: {count} file")
        
        if count > 0:
            self.start_queue_btn.config(state=tk.NORMAL)
            self.clear_queue_btn.config(state=tk.NORMAL)
        else:
            self.start_queue_btn.config(state=tk.DISABLED)
            self.clear_queue_btn.config(state=tk.DISABLED)
    
    def clear_queue(self):
        """Clear download queue"""
        if not self.pending_files:
            return
        
        confirm = messagebox.askyesno("Xác nhận", 
                                     f"Xóa {len(self.pending_files)} file trong Queue?")
        if confirm:
            self.pending_files.clear()
            self.update_queue_info()
            self.log("🗑️ Đã xóa Queue")
    
    def start_queue_download(self):
        """Start downloading all files in queue"""
        if not self.pending_files:
            messagebox.showwarning("Queue rỗng", "Không có file nào trong Queue!")
            return
        
        confirm = messagebox.askyesno("Xác nhận", 
                                     f"Bắt đầu tải {len(self.pending_files)} files từ Queue?\n\n"
                                     f"Thư mục lưu: {self.output_folder}")
        
        if not confirm:
            return
        
        self.log("=" * 50)
        self.log(f"🚀 BẮT ĐẦU TẢI {len(self.pending_files)} FILE TỪ QUEUE...")
        self.log(f"📁 Thư mục: {self.output_folder}")
        self.log("=" * 50)
        
        for file_info in self.pending_files:
            self.download_queue.put(file_info)
        
        # Clear pending queue
        self.pending_files.clear()
        self.update_queue_info()
        
        self.start_queue_btn.config(state=tk.DISABLED, text="⏳ Đang tải...")
        self.add_to_queue_btn.config(state=tk.DISABLED)
        
        self.max_concurrent = self.concurrent_var.get()
        for i in range(self.max_concurrent):
            threading.Thread(target=self.download_worker, daemon=True).start()
    
    def start_batch_download(self):
        """Start batch download of selected files"""
        selected_files = []
        for item in self.file_tree.get_children():
            if 'checked' in self.file_tree.item(item, 'tags'):
                values = self.file_tree.item(item, 'values')
                tags = self.file_tree.item(item, 'tags')
                
                url = None
                full_name = None
                scan_root = ""
                
                ext_val = ''
                type_val = ''
                for tag in tags:
                    if tag.startswith('http'):
                        url = tag
                    elif tag.startswith('scanroot::'):
                        scan_root = tag.split('scanroot::', 1)[1].strip()
                    elif tag.startswith('ext::'):
                        ext_val = tag.split('ext::', 1)[1]
                    elif tag.startswith('type::'):
                        type_val = tag.split('type::', 1)[1]
                    elif '/' in tag or '.' in tag:
                        full_name = tag
                
                if url and full_name:
                    selected_files.append({
                        'name': full_name,
                        'url': url,
                        'scan_root': scan_root,
                        'ext': locals().get('ext_val',''),
                        'file_type': locals().get('type_val','')
                    })
        
        if not selected_files:
            messagebox.showwarning("Không có file", "Vui lòng chọn ít nhất 1 file!")
            return
        
        confirm = messagebox.askyesno("Xác nhận", 
                                     f"Bắt đầu tải {len(selected_files)} files?\n\n"
                                     f"Thư mục lưu: {self.output_folder}")
        
        if not confirm:
            return
        
        self.log("=" * 50)
        self.log(f"🚀 BẮT ĐẦU TẢI {len(selected_files)} FILE...")
        self.log(f"📁 Thư mục: {self.output_folder}")
        self.log("=" * 50)
        
        for file_info in selected_files:
            # Normalize and ensure extension
            name_raw = file_info.get('name') or ''
            cleaned = self.clean_filename(name_raw)
            if file_info.get('ext'):
                cleaned = self.ensure_file_extension(cleaned, {'ext': file_info.get('ext'), 'file_type': file_info.get('file_type')})
            else:
                cleaned = self.ensure_file_extension(cleaned, {'file_type': file_info.get('file_type')})
            file_info['name'] = cleaned
            self.download_queue.put(file_info)
        
        self.start_queue_btn.config(state=tk.DISABLED, text="⏳ Đang tải...")
        self.add_to_queue_btn.config(state=tk.DISABLED)
        
        self.max_concurrent = self.concurrent_var.get()
        for i in range(self.max_concurrent):
            threading.Thread(target=self.download_worker, daemon=True).start()
    
    def download_worker(self):
        """Worker thread for downloading files"""
        while not self.download_queue.empty():
            try:
                file_info = self.download_queue.get(timeout=1)
                
                self.active_downloads += 1
                # Final sanitization of name before building path
                file_info['name'] = self.clean_filename(file_info.get('name'))
                self.log(f"⬇️ [{self.active_downloads}] Đang tải: {file_info['name']}")
                
                # Reset progress về 0%
                file_url = file_info['url']
                self.root.after(0, lambda: self.update_file_progress(file_url, 0))
                
                output_path = self.build_output_path(file_info)
                self.log(f"   💾 Lưu vào: {output_path}")
                
                # Download với callback progress
                success = self.try_ytdlp(file_info['url'], output_path, 
                                       progress_callback=lambda p: self.root.after(0, lambda: self.update_file_progress(file_url, p)))
                
                if not success:
                    success = self.download_file(file_info['url'], output_path,
                                                 progress_callback=lambda p: self.root.after(0, lambda: self.update_file_progress(file_url, p)))
                
                if success:
                    self.log(f"\u2705 [{self.active_downloads}] Ho\u00e0n th\u00e0nh: {file_info['name']}")
                    self.root.after(0, lambda: self.update_file_progress(file_url, 100))
                else:
                    # Fallback cu\u1ed1i: th\u1eed gdown
                    self.log(f"\ud83d\udd04 Th\u1eed gdown nh\u01b0 fallback cu\u1ed1i...")
                    success = self.try_gdown(file_info['url'], output_path)

                if success:
                    self.log(f"\u2705 [{self.active_downloads}] Ho\u00e0n th\u00e0nh: {file_info['name']}")
                    self.root.after(0, lambda: self.update_file_progress(file_url, 100))
                else:
                    self.log(f"\u274c [{self.active_downloads}] Th\u1ea5t b\u1ea1i: {file_info['name']}")
                    self.log(f"   \ud83d\udcbe T\u1ea1o file 0MB \u0111\u1ec3 \u0111\u00e1nh d\u1ea5u l\u1ed7i...")
                    
                    try:
                        with open(output_path, 'wb') as f:
                            pass
                        self.log(f"   \u2713 \u0110\u00e3 t\u1ea1o: {file_info['name']} (0MB)")
                    except Exception as create_err:
                        self.log(f"   \u26a0\ufe0f Kh\u00f4ng t\u1ea1o \u0111\u01b0\u1ee3c file 0MB: {create_err}")
                    
                    if file_url in self.file_tree_items:
                        item_id = self.file_tree_items[file_url]
                        current_values = list(self.file_tree.item(item_id, 'values'))
                        if len(current_values) >= 2:
                            current_values[1] = '\u274c L\u1ed7i (0MB)'
                            self.root.after(0, lambda iv=item_id, cv=current_values: self.file_tree.item(iv, values=cv))
                
                self.active_downloads -= 1
                self.download_queue.task_done()
                
            except Exception as e:
                self.log(f"❌ Lỗi worker: {str(e)}")
                import traceback
                self.log(f"   Chi tiết: {traceback.format_exc()}")
                
                try:
                    self.download_queue.task_done()
                except:
                    pass
                
                self.active_downloads -= 1
                continue
        
        if self.download_queue.empty() and self.active_downloads == 0:
            self.log("=" * 50)
            self.log("✅ ĐÃ HOÀN THÀNH TẤT CẢ!")
            self.log("=" * 50)
            self.progress_var.set("✅ Hoàn thành!")
            self.start_queue_btn.config(state=tk.NORMAL, text="⬇️ Tải Queue")
            self.add_to_queue_btn.config(state=tk.NORMAL)
            self.update_queue_info()
            messagebox.showinfo("Hoàn thành", 
                              f"✅ Đã tải xong tất cả file!\n\n"
                              f"📁 Vị trí: {self.output_folder}")

    def add_single_file(self):
        """Thêm file vào danh sách tải"""
        url = self.url_entry.get().strip()
        filename = self.filename_var.get().strip()
        
        if not url:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập link Google Drive!")
            return
        
        if not filename:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập tên file!")
            return
        
        display_text = f"{filename} | {url[:50]}..."
        self.single_listbox.insert(tk.END, display_text)
        self.single_listbox.itemconfig(tk.END, fg='#1a73e8')
        
        if not hasattr(self, 'single_files_data'):
            self.single_files_data = []
        self.single_files_data.append({'url': url, 'name': filename})
        
        self.url_entry.delete(0, tk.END)
        self.filename_var.set("video.mp4")
        
        self.update_single_count()
        
        self.log(f"➕ Đã thêm: {filename}")
    
    def auto_get_filename(self):
        """Ự động lấy tên file từ URL"""
        url = self.url_entry.get().strip()
        
        if not url:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập link Google Drive!")
            return
        
        self.log("🔍 Đang lấy tên file...")
        
        def fetch_thread():
            try:
                file_id = None
                patterns = [
                    r'/d/([a-zA-Z0-9_-]+)',
                    r'id=([a-zA-Z0-9_-]+)',
                    r'/file/d/([a-zA-Z0-9_-]+)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, url)
                    if match:
                        file_id = match.group(1)
                        break
                
                if not file_id:
                    self.log("❌ Không tìm thấy File ID trong URL")
                    messagebox.showerror("Lỗi", "URL không hợp lệ!\n\nVui lòng kiểm tra lại link Google Drive.")
                    return
                
                self.log(f"📌 File ID: {file_id}")
                
                if not self.cookies_file or not os.path.exists(self.cookies_file):
                    self.log("⚠️ Chưa có cookies - có thể không lấy được tên file private")
                
                file_info = None
                for attempt in range(3):
                    self.log(f"🔄 Thử lấy tên (lần {attempt + 1}/3)...")
                    file_info = self.get_file_info(file_id)
                    if file_info:
                        break
                    time.sleep(1)
                
                if file_info and file_info['name']:
                    cleaned_name = self.clean_filename(file_info['name'])
                    self.filename_var.set(cleaned_name)
                    
                    self.log(f"✅ Đã lấy tên: {cleaned_name}")
                    messagebox.showinfo("Thành công", f"✅ Tên file: {cleaned_name}\n\n👉 Nhấn '➕ Thêm' để thêm vào danh sách")
                else:
                    self.log("❌ Không lấy được tên file")
                    messagebox.showwarning("Cảnh báo", 
                                         "❌ Không lấy được tên file!\n\n"
                                         "Nguyên nhân có thể:\n"
                                         "• File bị hạn chế quyền truy cập\n"
                                         "• Chưa cung cấp cookies.txt\n"
                                         "• Link không đúng\n\n"
                                         "👉 Vui lòng nhập tên thủ công hoặc cung cấp cookies")
                    
            except Exception as e:
                self.log(f"❌ Lỗi: {str(e)}")
                messagebox.showerror("Lỗi", f"Không lấy được tên file:\n{str(e)}\n\n👉 Vui lòng nhập tên thủ công")
        
        threading.Thread(target=fetch_thread, daemon=True).start()
    
    def remove_single_files(self):
        """Xóa file đã chọn khỏi danh sách"""
        selected = self.single_listbox.curselection()
        if not selected:
            messagebox.showinfo("Thông báo", "Vui lòng chọn file cần xóa!")
            return
        
        for index in reversed(selected):
            self.single_listbox.delete(index)
            if hasattr(self, 'single_files_data') and index < len(self.single_files_data):
                del self.single_files_data[index]
        
        self.update_single_count()
        self.log(f"🗑️ Đã xóa {len(selected)} file")
    
    def clear_single_list(self):
        """Xóa toàn bộ danh sách"""
        if self.single_listbox.size() == 0:
            return
        
        confirm = messagebox.askyesno("Xác nhận", 
                                     f"Xóa tất cả {self.single_listbox.size()} file trong danh sách?")
        if confirm:
            self.single_listbox.delete(0, tk.END)
            self.single_files_data = []
            self.update_single_count()
            self.log("🗑️ Đã xóa toàn bộ danh sách")
    
    def update_single_count(self):
        """Cập nhật số lượng file"""
        count = self.single_listbox.size()
        self.single_count_var.set(f"{count} file")
        
        if count > 0:
            self.download_btn.config(state=tk.NORMAL)
        else:
            self.download_btn.config(state=tk.DISABLED)

    def start_single_download(self):
        """Start downloading all files in single tab"""
        if not hasattr(self, 'single_files_data') or len(self.single_files_data) == 0:
            messagebox.showwarning("Danh sách rỗng", "Vui lòng thêm file vào danh sách!")
            return
        
        confirm = messagebox.askyesno("Xác nhận", 
                                     f"Bắt đầu tải {len(self.single_files_data)} files?\n\n"
                                     f"Thư mục lưu: {self.output_folder}")
        
        if not confirm:
            return
        
        self.log("=" * 50)
        self.log(f"🚀 BẮT ĐẦU TẢI {len(self.single_files_data)} FILE...")
        self.log(f"📁 Thư mục: {self.output_folder}")
        self.log("=" * 50)
        
        for file_data in self.single_files_data:
            self.download_queue.put(file_data)
        
        self.single_listbox.delete(0, tk.END)
        self.single_files_data = []
        self.update_single_count()
        
        self.download_btn.config(state=tk.DISABLED, text="⏳ Đang tải...")
        
        self.max_concurrent = self.concurrent_var.get()
        for i in range(self.max_concurrent):
            threading.Thread(target=self.download_worker_simple, daemon=True).start()
    
    def download_worker_simple(self):
        """Worker cho single download (không update tree)"""
        while not self.download_queue.empty():
            try:
                file_info = self.download_queue.get(timeout=1)
                
                self.active_downloads += 1
                # Final sanitization of name before building path
                file_info['name'] = self.clean_filename(file_info.get('name'))
                self.log(f"⬇️ [{self.active_downloads}] Đang tải: {file_info['name']}")

                output_path = self.build_output_path(file_info)
                self.log(f"   💾 Lưu vào: {output_path}")
                
                success = self.try_ytdlp(file_info['url'], output_path)
                
                if not success:
                    success = self.download_file(file_info['url'], output_path)
                
                if success:
                    self.log(f"\u2705 [{self.active_downloads}] Ho\u00e0n th\u00e0nh: {file_info['name']}")
                else:
                    # Fallback cu\u1ed1i: th\u1eed gdown
                    self.log(f"\ud83d\udd04 Th\u1eed gdown nh\u01b0 fallback cu\u1ed1i...")
                    success = self.try_gdown(file_info['url'], output_path)

                if success:
                    self.log(f"\u2705 [{self.active_downloads}] Ho\u00e0n th\u00e0nh: {file_info['name']}")
                else:
                    self.log(f"\u274c [{self.active_downloads}] Th\u1ea5t b\u1ea1i: {file_info['name']}")
                    self.log(f"   \ud83d\udcbe T\u1ea1o file 0MB \u0111\u1ec3 \u0111\u00e1nh d\u1ea5u l\u1ed7i...")
                    
                    try:
                        with open(output_path, 'wb') as f:
                            pass
                        self.log(f"   \u2713 \u0110\u00e3 t\u1ea1o: {file_info['name']} (0MB)")
                    except Exception as create_err:
                        self.log(f"   \u26a0\ufe0f Kh\u00f4ng t\u1ea1o \u0111\u01b0\u1ee3c file 0MB: {create_err}")
                
                self.active_downloads -= 1
                self.download_queue.task_done()
                
            except Exception as e:
                self.log(f"❌ Lỗi worker: {str(e)}")
                import traceback
                self.log(f"   Chi tiết: {traceback.format_exc()}")
                
                try:
                    self.download_queue.task_done()
                except:
                    pass
                
                self.active_downloads -= 1
                continue
        
        if self.download_queue.empty() and self.active_downloads == 0:
            self.log("=" * 50)
            self.log("✅ ĐÃ HOÀN THÀNH TẤT CẢ!")
            self.log("=" * 50)
            self.progress_var.set("✅ Hoàn thành!")
            self.download_btn.config(state=tk.NORMAL, text="⬇️ TẢI TẤT CẢ")
            messagebox.showinfo("Hoàn thành", 
                              f"✅ Đã tải xong tất cả file!\n\n"
                              f"📁 Vị trí: {self.output_folder}")
    
    def log(self, message):
        """Add log message to queue for thread-safe logging"""
        self.log_queue.put(message)
    
    def process_log_queue(self):
        """Process log messages from queue (runs in main thread)"""
        try:
            while not self.log_queue.empty():
                message = self.log_queue.get_nowait()
                self.log_text.config(state=tk.NORMAL)
                
                if message.startswith("✅") or "thành công" in message.lower() or "hoàn thành" in message.lower():
                    self.log_text.insert(tk.END, message + "\n", "success")
                elif message.startswith("❌") or "lỗi" in message.lower() or "thất bại" in message.lower():
                    self.log_text.insert(tk.END, message + "\n", "error")
                elif message.startswith("⚠️") or "cảnh báo" in message.lower():
                    self.log_text.insert(tk.END, message + "\n", "warning")
                elif message.startswith("🔗") or message.startswith("📥") or message.startswith("🔍"):
                    self.log_text.insert(tk.END, message + "\n", "info")
                else:
                    self.log_text.insert(tk.END, message + "\n")
                
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.NORMAL)
        except:
            pass
        
        self.root.after(100, self.process_log_queue)
    
    def choose_cookies(self):
        """Choose cookies file"""
        file = filedialog.askopenfilename(
            title="Chọn file cookies.txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialdir=os.getcwd()
        )
        if file:
            self.cookies_file = file
            self.cookies_var.set(file)
            self.log(f"🍪 Đã chọn cookies: {os.path.basename(file)}")
    
    def choose_folder(self):
        """Choose output folder"""
        folder = filedialog.askdirectory(
            title="Chọn thư mục lưu file",
            initialdir=self.output_folder
        )
        if folder:
            self.output_folder = folder
            self.output_var.set(folder)
            self.log(f"📁 Đã chọn thư mục: {folder}")
    
    def download_file(self, url, output_path, progress_callback=None):
        """Download file from Google Drive"""
        file_id = None
        patterns = [
            r'/d/([a-zA-Z0-9_-]+)',
            r'id=([a-zA-Z0-9_-]+)',
            r'/file/d/([a-zA-Z0-9_-]+)',
        ]
        
        self.log(f"🔗 Đang phân tích URL: {url[:80]}...")
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                file_id = match.group(1)
                break
        
        if not file_id:
            self.log(f"❌ Không tìm thấy File ID trong URL")
            self.log(f"   URL đầy đủ: {url}")
            return False
        
        self.log(f"✅ File ID: {file_id}")
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        })
        session.verify = False
        
        if self.cookies_file and os.path.exists(self.cookies_file):
            try:
                self.log(f"🍪 Đang load cookies...")
                cookies = MozillaCookieJar(self.cookies_file)
                cookies.load(ignore_discard=True, ignore_expires=True)
                session.cookies = cookies
                self.log(f"✅ Đã load {len(session.cookies)} cookies")
            except Exception as e:
                self.log(f"⚠️ Không load được cookies: {str(e)}")
        
        self.log("⬇️ Phương pháp 1: Direct download...")
        
        try:
            # Google Drive hiện dùng /drive/uc thay vì /uc
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
            session.headers.update({
                'Referer': 'https://drive.google.com/',
                'Origin': 'https://drive.google.com',
            })
            response = session.get(download_url, stream=True, timeout=30, allow_redirects=True)
            
            if 'text/html' in response.headers.get('content-type', ''):
                self.log(f"⚠️ Phát hiện trang xác nhận (Status: {response.status_code})...")
                
                html = response.text
                confirm_token = None
                
                for key, value in response.cookies.items():
                    if key.startswith('download_warning'):
                        confirm_token = value
                        self.log(f"🍪 Tìm thấy token trong cookies: {key}={value}")
                        break
                
                if not confirm_token:
                    token_patterns = [
                        r'confirm=([a-zA-Z0-9_-]+)',
                        r'uuid=([a-zA-Z0-9_-]+)',
                        r'"downloadUrl":"[^"]*confirm=([^&"]+)',
                        r'action="[^"]*confirm=([^&"]+)',
                        r'confirm" value="([^"]+)',
                        r'name="uuid" value="([^"]+)',
                    ]
                    
                    for pattern in token_patterns:
                        match = re.search(pattern, html)
                        if match:
                            confirm_token = match.group(1)
                            self.log(f"✅ Tìm thấy token")
                            break
                
                if confirm_token:
                    self.log(f"✅ Confirm token: {confirm_token[:30]}...")
                    download_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={confirm_token}"
                    response = session.get(download_url, stream=True, timeout=30)
                    self.log(f"📥 Response: {response.status_code}")
                else:
                    self.log("⚠️ Không tìm thấy confirm token")
                    # Thử các URL thay thế
                    alt_urls = [
                        f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
                        f"https://drive.google.com/uc?id={file_id}&export=download&confirm=t",
                        f"https://drive.google.com/uc?id={file_id}",
                    ]
                    for alt_url in alt_urls:
                        response = session.get(alt_url, stream=True, timeout=30, allow_redirects=True)
                        if 'text/html' not in response.headers.get('content-type', ''):
                            break
                    
                    if 'text/html' in response.headers.get('content-type', ''):
                        return self.download_file_method2(session, file_id, output_path)
            
            content_type = response.headers.get('content-type', '')
            if 'text/html' in content_type:
                self.log("⚠️ Vẫn nhận được HTML, chuyển sang phương pháp 2...")
                return self.download_file_method2(session, file_id, output_path)
            
            total = int(response.headers.get('content-length', 0))
            
            if total > 0:
                self.log(f"📦 Kích thước: {total / (1024*1024):.2f} MB")
                self.log(f"⚡ Tốc độ: Chunk 4MB x {self.max_concurrent} luồng")
            else:
                self.log("📦 Đang tải...")
            
            downloaded = 0
            chunk_size = 4 * 1024 * 1024
            last_update = 0
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if downloaded - last_update >= chunk_size:
                            if total > 0:
                                percent = (downloaded / total) * 100
                                self.root.after(0, lambda p=percent: self.progress_bar.config(value=p))
                                self.root.after(0, lambda p=percent: self.progress_var.set(f"Đang tải... {p:.1f}%"))
                                if progress_callback:
                                    try:
                                        progress_callback(percent)
                                    except:
                                        pass
                            else:
                                self.root.after(0, lambda d=downloaded: self.progress_var.set(f"Đang tải... {d / (1024*1024):.1f} MB"))
                            last_update = downloaded
            
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                if file_size > 0:
                    self.log(f"✅ Đã tải {file_size / (1024*1024):.2f} MB")
                    return True
                else:
                    self.log("❌ File rỗng, thử phương pháp khác...")
                    return self.download_file_method2(session, file_id, output_path)
            
            return True
            
        except Exception as e:
            self.log(f"❌ Phương pháp 1 thất bại: {str(e)}")
            self.log("🔄 Chuyển sang phương pháp 2...")
            return self.download_file_method2(session, file_id, output_path)
    
    def download_file_method2(self, session, file_id, output_path):
        """Phương pháp 2: Download file bị hạn chế quyền"""
        self.log("⬇️ Phương pháp 2: View mode download...")
        
        try:
            view_urls = [
                f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
                f"https://drive.google.com/uc?id={file_id}&export=download&confirm=t",
                f"https://drive.google.com/u/0/uc?id={file_id}&export=download&confirm=t",
                f"https://drive.google.com/uc?id={file_id}&export=download&authuser=0",
            ]
            
            for i, url in enumerate(view_urls, 1):
                try:
                    self.log(f"🔗 Thử URL {i}/{len(view_urls)}...")
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': '*/*',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                    }
                    
                    response = session.get(url, stream=True, timeout=30, allow_redirects=True, headers=headers)
                    
                    self.log(f"   Status: {response.status_code}")
                    
                    if 'text/html' in response.headers.get('content-type', ''):
                        html = response.text
                        
                        if 'không cấp cho bạn quyền tải' in html or 'not given permission' in html.lower():
                            self.log("⚠️ File bị hạn chế download")
                            return self.download_restricted_file(session, file_id, output_path)
                        
                        continue
                    
                    if response.status_code == 200:
                        self.log(f"✅ Tìm thấy download link!")
                        
                        total = int(response.headers.get('content-length', 0))
                        if total > 0:
                            self.log(f"📦 Kích thước: {total / (1024*1024):.2f} MB")
                        
                        downloaded = 0
                        last_update = 0
                        chunk_size = 4*1024*1024
                        with open(output_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=chunk_size):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    if downloaded - last_update >= chunk_size:
                                        if total > 0:
                                            percent = (downloaded / total) * 100
                                            self.root.after(0, lambda p=percent: self.progress_bar.config(value=p))
                                            self.root.after(0, lambda p=percent: self.progress_var.set(f"Đang tải... {p:.1f}%"))
                                        else:
                                            self.root.after(0, lambda d=downloaded: self.progress_var.set(f"Đang tải... {d / (1024*1024):.1f} MB"))
                                        last_update = downloaded
                        
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                            return True
                
                except Exception as e:
                    self.log(f"⚠️ URL {i} thất bại: {str(e)}")
                    continue
            
            self.log("🔄 Chuyển sang phương pháp xem file...")
            return self.download_restricted_file(session, file_id, output_path)
            
        except Exception as e:
            self.log(f"❌ Lỗi phương pháp 2: {str(e)}")
            return False
    
    def download_restricted_file(self, session, file_id, output_path):
        """Phương pháp 3: Download file bị hạn chế bằng cách xem"""
        self.log("⬇️ Phương pháp 3: Restricted file download...")
        
        try:
            view_url = f"https://drive.google.com/file/d/{file_id}/view"
            self.log(f"🔗 Truy cập trang xem file...")
            
            response = session.get(view_url, timeout=30)
            
            if response.status_code != 200:
                self.log(f"❌ Không truy cập được: {response.status_code}")
                return False
            
            html = response.text
            
            patterns = [
                r'"downloadUrl":"([^"]+)"',
                r'"downloadUrl":\s*"([^"]+)"',
                r'\\"downloadUrl\\":\\"([^\\]+)\\"',
                r'"url":"(https://[^"]*googleusercontent[^"]*)"',
                r'"mediaDownloadUrl":"([^"]+)"',
                r'https://[a-z0-9-]+\.googleusercontent\.com/[^"\s<>]+',
                # Dạng encoded trong JSON string
                r'downloadUrl\\u0022:\\u0022([^\\]+)',
                r'"contentUrl":"([^"]+)"',
            ]
            
            download_url = None
            for pattern in patterns:
                matches = re.findall(pattern, html)
                if matches:
                    download_url = matches[0]
                    # Decode các ký tự đặc biệt
                    download_url = download_url.replace('\\u003d', '=').replace('\\u0026', '&')
                    download_url = download_url.replace('\\u003D', '=').replace('\\u0026', '&')
                    download_url = download_url.replace('%3D', '=').replace('%26', '&')
                    download_url = download_url.replace('\\/', '/')
                    self.log(f"✅ Tìm thấy download URL!")
                    break
            
            # Nếu vẫn không tìm được, thử drive.usercontent.google.com trực tiếp
            if not download_url:
                self.log("🔄 Thử drive.usercontent.google.com trực tiếp...")
                usercontent_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
                try:
                    r = session.get(usercontent_url, stream=True, timeout=20, allow_redirects=True)
                    if r.status_code == 200 and 'text/html' not in r.headers.get('content-type', ''):
                        self.log(f"✅ drive.usercontent thành công!")
                        total = int(r.headers.get('content-length', 0))
                        if total > 0:
                            self.log(f"📦 Kích thước: {total / (1024*1024):.2f} MB")
                        with open(output_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=4*1024*1024):
                                if chunk:
                                    f.write(chunk)
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                            return True
                except Exception as ue:
                    self.log(f"⚠️ drive.usercontent thất bại: {ue}")
            
            if not download_url:
                self.log("❌ Không tìm thấy download URL")
                self.log("💡 File cần quyền truy cập đặc biệt")
                return False
            
            self.log(f"⬇️ Đang tải từ googleusercontent...")
            response = session.get(download_url, stream=True, timeout=60)
            
            if response.status_code != 200:
                self.log(f"❌ Không download được: {response.status_code}")
                return False
            
            total = int(response.headers.get('content-length', 0))
            if total > 0:
                self.log(f"📦 Kích thước: {total / (1024*1024):.2f} MB")
            
            downloaded = 0
            last_update = 0
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=4*1024*1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if downloaded - last_update >= 1024*1024:
                            if total > 0:
                                percent = (downloaded / total) * 100
                                self.root.after(0, lambda p=percent: self.progress_bar.config(value=p))
                                self.root.after(0, lambda p=percent: self.progress_var.set(f"Đang tải... {p:.1f}%"))
                            else:
                                self.root.after(0, lambda d=downloaded: self.progress_var.set(f"Đang tải... {d / (1024*1024):.1f} MB"))
                            last_update = downloaded
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                self.log(f"✅ Đã tải {os.path.getsize(output_path) / (1024*1024):.2f} MB")
                return True
            
            return False
            
        except Exception as e:
            self.log(f"❌ Lỗi phương pháp 3: {str(e)}")
            return False
    
    def try_ytdlp(self, url, output_path, progress_callback=None):
        """Phương pháp download bằng yt-dlp (mạnh nhất)"""
        try:
            self.log("⬇️ Phương pháp YT-DLP: Trying yt-dlp...")
            
            try:
                result = subprocess.run(
                    ["yt-dlp", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    **self._subprocess_no_window_kwargs()
                )
                version = result.stdout.strip()
                self.log(f"✅ yt-dlp version: {version}")
            except FileNotFoundError:
                self.log("⚠️ yt-dlp chưa cài đặt!")
                self.log("💡 Cài: pip install yt-dlp")
                return False
            except Exception as e:
                self.log(f"⚠️ Không tìm thấy yt-dlp")
                return False
            
            cmd = [
                "yt-dlp",
                url,
                "-o", output_path,
                "--no-warnings",
                "--progress",
                "--newline",
                "--concurrent-fragments", "4",
                "--buffer-size", "16M",
                "--no-check-certificate",
                "--extractor-retries", "1",  # Giảm retry để fail nhanh hơn
                "--fragment-retries", "2",
                "--retries", "2",
                "--no-cache-dir",
                "--add-headers", "Referer:https://drive.google.com/",
                "--geo-bypass",
            ]
            
            if self.cookies_file and os.path.exists(self.cookies_file):
                cmd.extend(["--cookies", self.cookies_file])
                self.log(f"🍪 Dùng cookies: {os.path.basename(self.cookies_file)}")
            
            self.log("🔄 Đang download với yt-dlp...")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                **self._subprocess_no_window_kwargs()
            )
            
            gdrive_404_detected = False
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                
                # Detect lỗi GoogleDrive 404 sớm → terminate ngay
                if "GoogleDrive" in line and ("404" in line or "Unable to download" in line):
                    self.log(f"   ⚠️ Google Drive extractor lỗi 404 - bỏ qua yt-dlp")
                    gdrive_404_detected = True
                    process.terminate()
                    break
                    
                if "[download]" in line and "%" in line:
                    try:
                        match = re.search(r'(\d+\.?\d*)%', line)
                        if match:
                            percent = float(match.group(1))
                            self.root.after(0, lambda p=percent: self.progress_bar.config(value=p))
                            self.root.after(0, lambda p=percent: self.progress_var.set(f"Đang tải... {p:.1f}%"))
                            if progress_callback:
                                try:
                                    progress_callback(percent)
                                except:
                                    pass
                    except:
                        pass
                
                if any(x in line for x in ["download", "ERROR", "WARNING", "Destination"]):
                    self.log(f"   {line}")
            
            process.wait()
            
            if gdrive_404_detected:
                return False
            
            if process.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                if file_size > 0:
                    self.log(f"\u2705 yt-dlp download th\u00e0nh c\u00f4ng! ({file_size / (1024*1024):.2f} MB)")
                    return True
                else:
                    self.log("\u26a0\ufe0f File r\u1ed7ng, th\u1eed ph\u01b0\u01a1ng ph\u00e1p kh\u00e1c...")
                    return False
            else:
                self.log(f"\u26a0\ufe0f yt-dlp th\u1ea5t b\u1ea1i (exit code: {process.returncode})")
                return False
                
        except Exception as e:
            self.log(f"\u26a0\ufe0f L\u1ed7i yt-dlp: {str(e)}")
            return False

    def try_gdown(self, url, output_path):
        """Fallback: Download b\u1eb1ng gdown Python API (import tr\u1ef1c ti\u1ebfp t\u1eeb venv)"""
        # B\u01b0\u1edbc 1: import gdown t\u1eeb venv
        try:
            import gdown
            self.log(f"\u2705 gdown Python API: {gdown.__version__}")
        except ImportError:
            self.log("\u26a0\ufe0f gdown ch\u01b0a c\u00e0i trong venv - th\u1eed c\u00e0i...")
            try:
                import subprocess, sys
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q", "gdown"],
                    capture_output=True, text=True, timeout=60,
                    **self._subprocess_no_window_kwargs()
                )
                if result.returncode != 0:
                    self.log("\u274c Kh\u00f4ng c\u00e0i \u0111\u01b0\u1ee3c gdown")
                    return False
                import gdown
                self.log(f"\u2705 \u0110\u00e3 c\u00e0i gdown {gdown.__version__}")
            except Exception as ie:
                self.log(f"\u274c Kh\u00f4ng c\u00e0i \u0111\u01b0\u1ee3c gdown: {ie}")
                return False

        # B\u01b0\u1edbc 2: T\u00ecm file_id
        file_id = None
        for pat in [r'/file/d/([a-zA-Z0-9_-]+)', r'/d/([a-zA-Z0-9_-]+)', r'id=([a-zA-Z0-9_-]+)']:
            m = re.search(pat, url)
            if m:
                file_id = m.group(1)
                break

        if not file_id:
            self.log("\u274c gdown: Kh\u00f4ng t\u00ecm th\u1ea5y file ID")
            return False

        self.log(f"\u2b07\ufe0f gdown: t\u1ea3i file {file_id}...")
        drive_url = f"https://drive.google.com/uc?id={file_id}"

        try:
            # Ph\u00e1t hi\u1ec7n t\u1ef1 \u0111\u1ed9ng c\u00e1c params c\u00f3 s\u1eb5n trong gdown version hi\u1ec7n t\u1ea1i
            import inspect
            sig = inspect.signature(gdown.download)
            available = set(sig.parameters.keys())

            kwargs = {'output': output_path, 'quiet': False}
            if 'fuzzy' in available:
                kwargs['fuzzy'] = True
            if 'cookies_file' in available and self.cookies_file and os.path.exists(self.cookies_file):
                kwargs['cookies_file'] = self.cookies_file
                self.log(f"\ud83c\udf6a gdown d\u00f9ng cookies: {os.path.basename(self.cookies_file)}")

            out = gdown.download(drive_url, **kwargs)

            if out and os.path.exists(out) and os.path.getsize(out) > 0:
                self.log(f"\u2705 gdown th\u00e0nh c\u00f4ng! ({os.path.getsize(out) / (1024*1024):.2f} MB)")
                return True
            elif os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                self.log(f"\u2705 gdown th\u00e0nh c\u00f4ng! ({os.path.getsize(output_path) / (1024*1024):.2f} MB)")
                return True
            else:
                self.log("\u26a0\ufe0f gdown: file r\u1ed7ng ho\u1eb7c kh\u00f4ng t\u1ea3i \u0111\u01b0\u1ee3c")
                return False

        except Exception as e:
            err_msg = str(e)
            self.log(f"\u26a0\ufe0f gdown l\u1ed7i: {err_msg[:200]}")

            # N\u1ebfu gdown m\u1edbi kh\u00f4ng c\u00f3 'fuzzy', th\u1eed l\u1ea1i kh\u00f4ng c\u00f3 fuzzy
            if 'fuzzy' in err_msg or 'unexpected keyword' in err_msg:
                try:
                    kwargs.pop('fuzzy', None)
                    out = gdown.download(drive_url, **kwargs)
                    if out and os.path.exists(out) and os.path.getsize(out) > 0:
                        self.log(f"\u2705 gdown th\u00e0nh c\u00f4ng (no-fuzzy)! ({os.path.getsize(out) / (1024*1024):.2f} MB)")
                        return True
                except Exception as e2:
                    self.log(f"\u274c gdown l\u1ed7i (no-fuzzy): {str(e2)[:200]}")

            return False

# ========== MAIN ==========
if __name__ == "__main__":
    root = tk.Tk()
    app = SimpleDriveDownloader(root)
    root.mainloop()