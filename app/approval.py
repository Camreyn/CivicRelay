"""Independent local human gate. No HTTP/MCP parameter can assert approval."""
def confirm(title,text,button='Approve',seconds=120):
    import tkinter as tk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText
    root=tk.Tk();root.title(title);root.geometry('920x720');root.minsize(660,500)
    result=False
    ttk.Label(root,text=title,font=('Segoe UI',17,'bold'),padding=18).pack(anchor='w')
    area=ScrolledText(root,wrap='word',font=('Segoe UI',11));area.pack(fill='both',expand=True,padx=18,pady=8)
    area.insert('1.0',text);area.configure(state='disabled')
    accepted=tk.BooleanVar(value=False)
    ttk.Checkbutton(root,text='I reviewed the exact content, destination, and privacy implications shown above.',variable=accepted).pack(anchor='w',padx=18,pady=12)
    buttons=ttk.Frame(root,padding=18);buttons.pack(fill='x')
    def approve():
        nonlocal result
        if accepted.get():result=True;root.destroy()
    ttk.Button(buttons,text=button,command=approve).pack(side='right')
    ttk.Button(buttons,text='Cancel',command=root.destroy).pack(side='right',padx=10)
    ttk.Label(buttons,text='Closes without approval after two minutes.').pack(side='left')
    root.after(seconds*1000,root.destroy);root.lift();root.mainloop()
    return result
