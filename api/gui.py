def drawText(surface, text, color, rect, font, aa=False, bkg=None): #text wrapping function from https://www.pygame.org/wiki/TextWrap
    rect = pygame.Rect(rect)
    y = rect.top
    lineSpacing = -2

    # get the height of the font
    fontHeight = font.size("Tg")[1]

    while text:
        i = 1

        # determine if the row of text will be outside our area
        if y + fontHeight > rect.bottom:
            break

        # determine maximum width of line
        while font.size(text[:i])[0] < rect.width and i < len(text):
            i += 1

        # if we've wrapped the text, then adjust the wrap to the last word      
        if i < len(text): 
            i = text.rfind(" ", 0, i) + 1

        # render the line and blit it to the surface
        if bkg:
            image = font.render(text[:i], 1, color, bkg)
            image.set_colorkey(bkg)
        else:
            image = font.render(text[:i], aa, color)

        surface.blit(image, (rect.left, y))
        y += fontHeight + lineSpacing

        # remove the text we just blitted
        text = text[i:]

    return text


#basic button class
class Button:
    def __init__(self,size,font_path,pos,text='Button',font_size=12,color=(255,255,255),textcolor=(0,0,0)):
        self.surface = pygame.Surface(size)
        self.size = size
        self.surface.fill(color)
        self.font = pygame.font.Font(font_path,font_size)
        self.pos = pos
        self.clicked = False
        remaining = drawText(self.surface,text,textcolor,pygame.Rect(2,2,self.size[0]-4,self.size[1]-4),self.font,aa=True)
        if remaining:
            print('Warning: "'+remaining+'" left the bounding box and could not be rendered.')
    
    def check_click(self):
        if pygame.Rect(self.pos,self.size).collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
            if not self.clicked:
                self.clicked = True
                return True
        else:
            self.clicked = False