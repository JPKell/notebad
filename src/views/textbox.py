from collections import deque
from tkinter import Text, Canvas, IntVar
from tkinter.ttk import Notebook, Scrollbar, Frame

from conf import cf
from .colors import Themes
from .syntax import SyntaxMarker

class Textbox(Text):
    ''' This is where the magic happens. This is the text area where the user 
        is typing. This class is responsible for the text area, line numbers, 
        and scrollbars. Syntax highlighting is a beast of it's own and is 
        separated into it's own module. '''
    def __init__(self, tabs:Notebook) -> None:
        # tabs is the parent widget
        self.tabs = tabs
        self.font = tabs.view.ui.font
        self.font_size = 0  # This allows different font sizes between windows
        # This frame houses the text area, line numbers and scrollbars
        self.frame = Frame(tabs)
        # Initialize the text area
        super().__init__(self.frame, undo=True, border=0, relief='flat', wrap='none') 
        # Instantiate the line numbers
        self._make_line_numbers()
        # Instantiate the scrollbar
        self._make_scrollbars()

        # File settings
        self.full_path = ""
        self.file_path  = ""
        self._file_name = cf.new_file_name
        self.tk_name    = ""
        self.changed_since_saved = False

        # Stack for undo/redo
        self.stack = deque(maxlen = cf.max_undo)
        self.stackcursor = 0 

        # Text area settings
        self._make_text_area(tabs) 
        
        # This is currently the primary way to check if the line numbers
        # need to be redrawn. This may need to be changed when the language server 
        # is updated (created).  
        self.bind('<Key>', lambda event: self.check_on_key(event))  

        # Syntax highlighting. Until this is a little more stable I don't want 
        # it to be the default
        if cf.enable_syntax_highlighting:
            self._setup_syntax_highlighting()

    ###              ###
    # Class properties #
    ###              ###

    @property
    def is_blank(self) -> bool:
        ''' Returns True if the text area has not had a single character entered. 
            By default a text area will house a new line character. So len is not
            a good way to check if the text area is blank.
        '''
        return self.get(1.0, 'end') == '\n'
    
    @property
    def file_name(self) -> str:
        return self._file_name
    
    @file_name.setter
    def file_name(self, file_name:str) -> None:
        ''' Updating the filename will also update the tab name '''
        self._file_name = file_name
        self.tabs.tab(self.tk_name, text=file_name)

    ###                        ###
    # Underlying file operations #
    ###                        ###

    def set_meta(self, file_path:str=None, file_name:str=None, full_path:str=None, tk_name:str=None) -> None:
        ''' Set various pieces of meta data. The tk name is the name of the tab in 
            tkinter land '''
        self.tk_name = tk_name      if tk_name   else self.tk_name
        self.file_path = file_path  if file_path else self.file_path
        self.file_name = file_name  if file_name else self.file_name
        self.full_path = full_path  if full_path else self.full_path

    ###              ###  
    # Get and set text #
    ###              ###

    def get_current_line_text(self) -> str:
        ''' Return the text of the current line including the newline character '''
        return self.get('insert linestart', 'insert lineend')

    def get_selection(self) -> str:
        ''' Return the text selected in the textbox '''
        # Throws an error if there is no selection so we look for the tag first
        if self.tag_ranges('sel') == (): 
            return ""
        else:
            return self.get('sel.first', 'sel.last')

    def clear_all(self):
        self.delete("1.0", "end")

    ###                        ### 
    # Text selections and cursor #
    ###                        ###

    def select_all(self) -> None:
        ''' Select all text in the textbox '''
        self.tag_add('sel', 1.0, 'end')

    def delete_selection(self):
        self.delete('sel.first', 'sel.last')

    ###           ###
    # Undo and redo #
    ###           ###

    # This whole section needs to be thought about more carefully. There are 
    # a couple of considerations. The standard undo/redo is not very good and
    # the granularity is too large. I would like to be able to undo/redo into 
    # a distant past, but I don't want to store every single keystroke. 
    # I think I want to see this implimented with a shifting granularity. So 
    # the first handful of undo/redo's are at the character level, then the
    # next bunch are at the word level and then statement level. 
    # Implementation has not been thought out yet.

    def stackify(self):
        self.stack.append(self.get("1.0", "end - 1c"))
        if self.stackcursor < 9: self.stackcursor += 1
 
    def undo(self):
        if self.stackcursor != 0:
            self.clear()
            if self.stackcursor > 0: self.stackcursor -= 1
            self.insert("0.0", self.stack[self.stackcursor])
 
    def redo(self):
        if len(self.stack) > self.stackcursor + 1:
            self.clear()
            if self.stackcursor < 9: self.stackcursor += 1
            self.insert("0.0", self.stack[self.stackcursor])
 

    ####################
    ## Event handlers ##
    ####################

    def check_on_key(self, event) -> None:
        ''' This is the function that runs upon every keypress. If there is a
            way to do any of these outside of checking every keystroke that's 
            a better option. The functions called from here tend to be blocking
            and will cause user input to be delayed. 
        
            Event state 16 is when no modifier keys are pressed. It will not 
            fire when shift and an alphanumeric key is pressed.'''
        
        # Check if the document has been updated since last saved
        if not self.changed_since_saved and event.state == 16:
            self.changed_since_saved = True
            self.tabs.set_properties(self.tk_name, text=f'{self.file_name} *')

        # Put a delay on this so the cursor has a chance to move with the character
        # placed on the screen before we update the position. 
        self.after(10, self.tabs.view.footer.update_pos)

        # Pushes the current state of the document onto the stack for undo
        self.stackify()
        
        # This is insane. The syntax highlighting goes over the whole document 
        # every keystroke
        if cf.enable_syntax_highlighting:
            self.syntax.tagHighlight()
            self.syntax.scan()

    ## Scrollbar events ##
    def hide_unused_scrollbars(self) -> None:
        ''' This checks the scrollbars to see if they are needed. 
            Currently the vertical scrollbar is always visible and
            the horizontal scrollbar is only visible when needed.

            The vertical scrollbar could be hidden but it needs more logic
            to work well with opening files that are longer than the window.
        '''
        hori_bar = self.horiz_scroll.get()

        if hori_bar[0] == 0 and hori_bar[1] == 1 :
            if self.horiz_scroll_visible == True:
                self.horiz_scroll_visible = False
                self.horiz_scroll.pack_forget()
        else:
            if self.horiz_scroll_visible == False:
                self.horiz_scroll_visible == True
                self.horiz_scroll.pack(expand=True, side='right', fill='x')

    def _on_change(self, event):
        self.linenumbers.redraw()

    ###                 ###
    # Constructor helpers #
    ###                 ###

    def _make_text_area(self, tabs:Notebook) -> None:
        ''' Create a new textbox and add it to the notebook '''
        if tabs.view.ui.theme == 'dark':
            colors = Themes.dark
        else:
            colors = Themes.light
        self.configure(
            background=colors.text_background,          
            foreground=colors.text_foreground,
            highlightbackground=colors.text_background, # These 2 remove the quasi borders 
            highlightcolor=colors.text_background,      # around the textbox
            font=self.font,
            padx=5, 
            pady=5)
        self.pack(expand=True, fill='both')
        tabs.add(self.frame)
            
        self.linenumbers.itemconfigure("lineno", fill=colors.text_foreground)
        self.linenumbers.config(
            bg=colors.background, 
            highlightbackground=colors.background
            )

    def _make_line_numbers(self) -> None:
        ''' Add line numbers Canvas to the text area '''
        linenumbers = TextLineNumbers(self.frame, width=cf.line_number_width)
        linenumbers.attach(self)
        linenumbers.pack(side="left", fill="y")
        self.linenumbers = linenumbers
        self.bind("<<Change>>", self._on_change)
        self.bind("<Configure>", self._on_change)

    def _make_scrollbars(self) -> None:
        ''' Add vertical and horizontal scrollbars to the text area '''
        # Add scrollbars to text area
        self.vert_scroll=Scrollbar(self.frame, orient='vertical')
        self.vert_scroll.pack(side='right', fill='y')
        self.vert_scroll_visible = False
        self.horiz_scroll=Scrollbar(self.frame, orient='horizontal')
        self.horiz_scroll_visible = False

        # The scrollbars require a connection both ways. So changes to one will
        # be reflected in the other.

        # Connect the scrollbars to the text area
        self.configure(
            xscrollcommand=self.horiz_scroll.set, 
            yscrollcommand=self.vert_scroll.set
            )
        # Connect the text area to the scrollbars
        self.horiz_scroll.config(command=self.xview)
        self.vert_scroll.config(command=self.yview)

    def _setup_syntax_highlighting(self) -> None:
        ''' This creates a proxy method for the text widget that will 
            intercept any events and call the syntax highlighter. 
            I would like to get rid of the proxy because it does not play well 
            with try catch blocks. Something will get caught in the proxy and
            fail in the original. 
        '''
        self.syntax = SyntaxMarker(self)
        # create a proxy for the underlying widget
        self._orig = self._w + "_orig"
        self.tk.call("rename", self._w, self._orig)
        self.tk.createcommand(self._w, self._proxy_for_line_numbers)

    def _proxy_for_line_numbers(self, *args):
        ''' This proxy currently works to enable the line numbers to update '''
        # let the actual widget perform the requested action
        
        # An event at the Text widget will be sent to the widget. The event
        # will be intercepted by the proxy and passed to the original widget. 
        
        cmd = (self._orig,) + args   # Here the command is rebuilt

        # This is a really bad idea. I want to crash the program if something is bad. 
        # But the proxy prevents other try blocks from working. Also if the program
        # crashes it will not save the file. This proxy business is balls and has to go. 
        if cf.dev_mode:
            try:
                result = self.tk.call(cmd)   # and executed with the original widget
            except Exception as e:
                print(e)
                print(cmd)
        else:
            result = self.tk.call(cmd)


        # generate an event if something was added or deleted,
        # or the cursor position changed
        if (args[0] in ("insert", "replace", "delete") or 
            args[0:3] == ("mark", "set", "insert") or
            args[0:2] == ("xview", "moveto") or
            args[0:2] == ("xview", "scroll") or
            args[0:2] == ("yview", "moveto") or
            args[0:2] == ("yview", "scroll")
        ):
            self.event_generate("<<Change>>", when="tail")

        # return what the actual widget returned
        return result 

    ###              ###
    # Pending removal? # 
    ###              ###


    def auto_indent(self, widget):
        ''' This method came from a tutorial online and I kinda like the idea,
            but I am not sure if it's worth the effort right now. '''
 
        index1 = widget.index("insert")
        index2 = "%s-%sc" % (index1, 1)
        prevIndex = widget.get(index2, index1)
 
        prevIndentLine = widget.index(index1 + "linestart")
        print("prevIndentLine ",prevIndentLine)
        prevIndent = self.getIndex(prevIndentLine)
        print("prevIndent ", prevIndent)
 
 
        if prevIndex == ":":
            widget.insert("insert", "\n" + "    ")
            widget.mark_set("insert", "insert + 1 line + 4char")
 
            while widget.compare(prevIndent, ">", prevIndentLine):
                widget.insert("insert", "     ")
                widget.mark_set("insert", "insert + 4 chars")
                prevIndentLine += "+4c"
            return "break"
         
        elif prevIndent != prevIndentLine:
            widget.insert("insert", "\n")
            widget.mark_set("insert", "insert + 1 line")
 
            while widget.compare(prevIndent, ">", prevIndentLine):
                widget.insert("insert", "     ")
                widget.mark_set("insert", "insert + 4 chars")
                prevIndentLine += "+4c"
            return "break"
        
    def getIndex(self, index) -> str:
        ''' Used by auto indent '''
        while True:
            if self.get(index) == " ":
                index = "%s+%sc" % (index, 1)
            else:
                return self.index(index)   
 


class TextLineNumbers(Canvas):
    ''' Line numbers for the edge of a textbox. These are drawn on a canvas 
        and are updated when the window is changed. ''' 
    def __init__(self, *args, **kwargs):
        Canvas.__init__(self, *args,**kwargs)
        self.textwidget = None
        self.color = 'grey'

    def attach(self, text_widget: Textbox) -> None:
        ''' Attach the line numbers to a textbox to retrive line info. '''
        self.textwidget = text_widget

    def redraw(self, *args) -> None:
        ''' Redraw the line numbers on the canvas '''
        self.delete("all")

        i = self.textwidget.index("@0,0")
        # Enter the endless loop
        while True:
            # Get the line dimensions in tuple (x,y,width,height,baseline)
            dline= self.textwidget.dlineinfo(i)
            # Leave the loop if the line is empty
            if dline is None: 
                break
            # Get the y coordinate of the line
            y = dline[1] - 2
            # Get the line number
            linenum = str(i).split(".")[0]
            # Set the font size
            size = 10
            # 10,000+ lines should be small. Or make the canvas bigger. I like font smaller. 
            if len(linenum) > 4:
                size = 7
            self.create_text(
                2,                      # x coordinate of the text. 
                y,
                anchor="nw", 
                text=linenum,           
                font=('arial',size), 
                tags='lineno',          # Let us get the line numbers later
                fill=self.color         
                )
            # Get the next line
            i = self.textwidget.index("%s+1line" % i)