# From the original eb library:
#   "There are some books that EB Library sets wrong character code of
#   the book.  They are written in JIS X 0208, but the library sets
#   ISO 8859-1.
#
#   We fix the character of the books.  The following table lists
#   titles of the first subbook in those books."

# TODO implement this...

# fix_encoding maps title -> encoding
fix_encoding = {
    # SONY DataDiskMan (DD-DR1) accessories.
    "%;%s%A%e%j!\\%S%8%M%9!\\%i%&%s": 'jisx0208',

    # Shin Eiwa Waei Chujiten (earliest edition)
    "8&5f<R!!?71QOBCf<-E5": 'jisx0208',

    # EB Kagakugijutsu Yougo Daijiten (YRRS-048)
    "#E#B2J3X5;=QMQ8lBg<-E5": 'jisx0208',

    # Nichi-Ei-Futsu Jiten (YRRS-059)
    "#E#N#G!?#J#A#N!J!\\#F#R#E!K": 'jisx0208',

    # Japanese-English-Spanish Jiten (YRRS-060)
    "#E#N#G!?#J#A#N!J!\\#S#P#A!K": 'jisx0208',

    # Panasonic KX-EBP2 accessories.
    "%W%m%7!<%I1QOB!&OB1Q<-E5": 'jisx0208',
}
