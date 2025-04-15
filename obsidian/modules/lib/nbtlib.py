"""
Modified NBT Editor Code From https://github.com/twoolie/NBT
Edited To Work On Older Minecraft Versions
+ Few Minor Changes (Typing, Formatting, Etc.)

!! Licensed Under MIT License !!



Handle the NBT (Named Binary Tag) data format
For more information about the NBT format:
https://minecraft.gamepedia.com/NBT_format
"""

from struct import Struct, error as StructError
from gzip import GzipFile
from collections.abc import MutableMapping, MutableSequence, Sequence

# type: ignore
from obsidian.module import Module, AbstractModule


@Module(
    "NBTLib",
    description="Helper Library For for all NBT processing",
    author="Obsidian",
    version="1.0.0",
)
class NBTLib(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    unicode = str
    basestring = str

    TAG_END = 0
    TAG_BYTE = 1
    TAG_SHORT = 2
    TAG_INT = 3
    TAG_LONG = 4
    TAG_FLOAT = 5
    TAG_DOUBLE = 6
    TAG_BYTE_ARRAY = 7
    TAG_STRING = 8
    TAG_LIST = 9
    TAG_COMPOUND = 10
    TAG_INT_ARRAY = 11
    TAG_LONG_ARRAY = 12

    class MalformedFileError(Exception):
        """Exception raised on parse error."""

    class TAG():
        """TAG, a variable with an intrinsic name."""
        id = None
        fmt = None

        def __init__(self, value=None, name=None):
            self.name = name
            self.value = value

        # Parsers and Generators
        def _parse_buffer(self, buffer):
            raise NotImplementedError(self.__class__.__name__)

        def _render_buffer(self, buffer):
            raise NotImplementedError(self.__class__.__name__)

        # Printing and Formatting of tree
        def tag_info(self):
            """Return Unicode string with class, name and unnested value."""
            return self.__class__.__name__ + (
                f'({self.name})' if self.name
                else "") + ": " + self.valuestr()

        def valuestr(self):
            """Return Unicode string of unnested value. For iterators, this
            returns a summary."""
            return NBTLib.unicode(self.value)

        def pretty_tree(self, indent=0):
            """Return formated Unicode string of self, where iterable items are
            recursively listed in detail."""
            return ("\t" * indent) + self.tag_info()

        # Python 2 compatibility; Python 3 uses __str__ instead.
        def __unicode__(self):
            """Return a unicode string with the result in human readable format.
            Unlike valuestr(), the result is recursive for iterators till at least
            one level deep."""
            return NBTLib.unicode(self.value)

        def __str__(self):
            """Return a string (ascii formated for Python 2, unicode for Python 3)
            with the result in human readable format. Unlike valuestr(), the result
            is recursive for iterators till at least one level deep."""
            return str(self.value)

        # Unlike regular iterators, __repr__() is not recursive.
        # Use pretty_tree for recursive results.
        # iterators should use __repr__ or tag_info for each item, like
        #  regular iterators
        def __repr__(self):
            """Return a string (ascii formated for Python 2, unicode for Python 3)
            describing the class, name and id for debugging purposes."""
            return f"<{self.__class__.__name__}({self.name}) at 0x{id(self):x}>"

    class _TAG_Numeric(TAG):
        """_TAG_Numeric, comparable to int with an intrinsic name"""

        def __init__(self, value=None, name=None, buffer=None):
            super(NBTLib._TAG_Numeric, self).__init__(value, name)
            if buffer:
                self._parse_buffer(buffer)

        # Parsers and Generators
        def _parse_buffer(self, buffer):
            # Note: buffer.read() may raise an IOError, for example if buffer is a
            # corrupt gzip.GzipFile
            self.value = self.fmt.unpack(buffer.read(self.fmt.size))[0]

        def _render_buffer(self, buffer):
            buffer.write(self.fmt.pack(self.value))

    class _TAG_End(TAG):
        fmt = Struct(">b")

        def __init__(self, value=None, name=None, buffer=None):
            super().__init__(value, name)
            self.id = NBTLib.TAG_END

        def _parse_buffer(self, buffer):
            # Note: buffer.read() may raise an IOError, for example if buffer is a
            # corrupt gzip.GzipFile
            value = self.fmt.unpack(buffer.read(1))[0]
            if value != 0:
                raise ValueError(f"A Tag End must be rendered as '0', not as '{value}'.")

        def _render_buffer(self, buffer):
            buffer.write(b'\x00')

    # == Value Tags ==#
    class TAG_Byte(_TAG_Numeric):
        """Represent a single tag storing 1 byte."""
        fmt = Struct(">b")

        def __init__(self, value=None, name=None, buffer=None):
            super().__init__(value, name, buffer)
            self.id = NBTLib.TAG_BYTE

    class TAG_Short(_TAG_Numeric):
        """Represent a single tag storing 1 short."""
        fmt = Struct(">h")

        def __init__(self, value=None, name=None, buffer=None):
            super().__init__(value, name, buffer)
            self.id = NBTLib.TAG_SHORT

    class TAG_Int(_TAG_Numeric):
        """Represent a single tag storing 1 int."""
        fmt = Struct(">i")

        def __init__(self, value=None, name=None, buffer=None):
            super().__init__(value, name, buffer)
            self.id = NBTLib.TAG_INT
        """Struct(">i"), 32-bits integer, big-endian"""

    class TAG_Long(_TAG_Numeric):
        """Represent a single tag storing 1 long."""
        fmt = Struct(">q")

        def __init__(self, value=None, name=None, buffer=None):
            super().__init__(value, name, buffer)
            self.id = NBTLib.TAG_LONG

    class TAG_Float(_TAG_Numeric):
        """Represent a single tag storing 1 IEEE-754 floating point number."""
        fmt = Struct(">f")

        def __init__(self, value=None, name=None, buffer=None):
            super().__init__(value, name, buffer)
            self.id = NBTLib.TAG_FLOAT

    class TAG_Double(_TAG_Numeric):
        """Represent a single tag storing 1 IEEE-754 double precision floating
        point number."""
        fmt = Struct(">d")

        def __init__(self, value=None, name=None, buffer=None):
            super().__init__(value, name, buffer)
            self.id = NBTLib.TAG_DOUBLE

    class TAG_Byte_Array(TAG, MutableSequence):
        """
        TAG_Byte_Array, comparable to a collections.UserList with
        an intrinsic name whose values must be bytes
        """

        def __init__(self, name=None, buffer=None):
            # TODO: add a value parameter as well
            self.id = NBTLib.TAG_BYTE_ARRAY
            super(NBTLib.TAG_Byte_Array, self).__init__(name=name)
            if buffer:
                self._parse_buffer(buffer)

        # Parsers and Generators
        def _parse_buffer(self, buffer):
            length = NBTLib.TAG_Int(buffer=buffer)
            self.value = bytearray(buffer.read(length.value))

        def _render_buffer(self, buffer):
            length = NBTLib.TAG_Int(len(self.value))
            length._render_buffer(buffer)
            buffer.write(bytes(self.value))

        # Mixin methods
        def __len__(self):
            return len(self.value)

        def __iter__(self):
            return iter(self.value)

        def __contains__(self, item):
            return item in self.value

        def __getitem__(self, key):
            return self.value[key]

        def __setitem__(self, key, value):
            # TODO: check type of value
            self.value[key] = value

        def __delitem__(self, key):
            del self.value[key]

        def insert(self, key, value):
            # TODO: check type of value, or is this done by self.value already?
            self.value.insert(key, value)

        # Printing and Formatting of tree
        def valuestr(self):
            return f"[{len(self.value)} byte(s)]"

        def __unicode__(self):
            return f'[{",".join([NBTLib.unicode(x) for x in self.value])}]'

        def __str__(self):
            return f'[{",".join([str(x) for x in self.value])}]'

    class TAG_Int_Array(TAG, MutableSequence):
        """
        TAG_Int_Array, comparable to a collections.UserList with
        an intrinsic name whose values must be integers
        """

        def __init__(self, name=None, buffer=None):
            # TODO: add a value parameter as well
            self.id = NBTLib.TAG_INT_ARRAY
            super(NBTLib.TAG_Int_Array, self).__init__(name=name)
            if buffer:
                self._parse_buffer(buffer)

        def update_fmt(self, length):
            """ Adjust struct format description to length given """
            self.fmt = Struct(">" + str(length) + "i")

        # Parsers and Generators
        def _parse_buffer(self, buffer):
            length = NBTLib.TAG_Int(buffer=buffer).value
            self.update_fmt(length)
            self.value = list(self.fmt.unpack(buffer.read(self.fmt.size)))

        def _render_buffer(self, buffer):
            length = len(self.value)
            self.update_fmt(length)
            NBTLib.TAG_Int(length)._render_buffer(buffer)
            buffer.write(self.fmt.pack(*self.value))

        # Mixin methods
        def __len__(self):
            return len(self.value)

        def __iter__(self):
            return iter(self.value)

        def __contains__(self, item):
            return item in self.value

        def __getitem__(self, key):
            return self.value[key]

        def __setitem__(self, key, value):
            self.value[key] = value

        def __delitem__(self, key):
            del self.value[key]

        def insert(self, key, value):
            self.value.insert(key, value)

        # Printing and Formatting of tree
        def valuestr(self):
            return f"[{len(self.value)} int(s)]"

    class TAG_Long_Array(TAG, MutableSequence):
        """
        TAG_Long_Array, comparable to a collections.UserList with
        an intrinsic name whose values must be integers
        """

        def __init__(self, name=None, buffer=None):
            self.id = NBTLib.TAG_LONG_ARRAY
            super(NBTLib.TAG_Long_Array, self).__init__(name=name)
            if buffer:
                self._parse_buffer(buffer)

        def update_fmt(self, length):
            """ Adjust struct format description to length given """
            self.fmt = Struct(f">{str(length)}q")

        # Parsers and Generators
        def _parse_buffer(self, buffer):
            length = NBTLib.TAG_Int(buffer=buffer).value
            self.update_fmt(length)
            self.value = list(self.fmt.unpack(buffer.read(self.fmt.size)))

        def _render_buffer(self, buffer):
            length = len(self.value)
            self.update_fmt(length)
            NBTLib.TAG_Int(length)._render_buffer(buffer)
            buffer.write(self.fmt.pack(*self.value))

        # Mixin methods
        def __len__(self):
            return len(self.value)

        def __iter__(self):
            return iter(self.value)

        def __contains__(self, item):
            return item in self.value

        def __getitem__(self, key):
            return self.value[key]

        def __setitem__(self, key, value):
            self.value[key] = value

        def __delitem__(self, key):
            del self.value[key]

        def insert(self, key, value):
            self.value.insert(key, value)

        # Printing and Formatting of tree
        def valuestr(self):
            return f"[{len(self.value)} long(s)]"

    class TAG_String(TAG, Sequence):
        """
        TAG_String, comparable to a collections.UserString with an
        intrinsic name
        """

        def __init__(self, value=None, name=None, buffer=None):
            self.id = NBTLib.TAG_STRING
            super(NBTLib.TAG_String, self).__init__(value, name)
            if buffer:
                self._parse_buffer(buffer)

        # Parsers and Generators
        def _parse_buffer(self, buffer):
            length = NBTLib.TAG_Short(buffer=buffer)
            read = buffer.read(length.value)
            if len(read) != length.value:
                raise StructError()
            self.value = read.decode("utf-8")

        def _render_buffer(self, buffer):
            save_val = self.value.encode("utf-8")
            length = NBTLib.TAG_Short(len(save_val))
            length._render_buffer(buffer)
            buffer.write(save_val)

        # Mixin methods
        def __len__(self):
            return len(self.value)

        def __iter__(self):
            return iter(self.value)

        def __contains__(self, item):
            return item in self.value

        def __getitem__(self, key):
            return self.value[key]

        # Printing and Formatting of tree
        def __repr__(self):
            return self.value

    # == Collection Tags ==#
    class TAG_List(TAG, MutableSequence):
        """
        TAG_List, comparable to a collections.UserList with an intrinsic name
        """

        def __init__(self, typ=None, value=None, name=None, buffer=None):
            self.id = NBTLib.TAG_LIST
            super(NBTLib.TAG_List, self).__init__(value, name)
            if typ:
                self.tagID = typ.id
            else:
                self.tagID = None
            self.tags = []
            if buffer:
                self._parse_buffer(buffer)
            # if self.tagID == None:
            #     raise ValueError("No type specified for list: %s" % (name))

        # Parsers and Generators
        def _parse_buffer(self, buffer):
            self.tagID = NBTLib.TAG_Byte(buffer=buffer).value
            self.tags = []
            length = NBTLib.TAG_Int(buffer=buffer)
            for _ in range(length.value):
                self.tags.append(NBTLib.TAGLIST[self.tagID](buffer=buffer))

        def _render_buffer(self, buffer):
            NBTLib.TAG_Byte(self.tagID)._render_buffer(buffer)
            length = NBTLib.TAG_Int(len(self.tags))
            length._render_buffer(buffer)
            for i, tag in enumerate(self.tags):
                if tag.id != self.tagID:
                    raise ValueError(
                        f"List element {i}({tag}) has type {tag.id} != container type {self.tagID}")
                tag._render_buffer(buffer)

        # Mixin methods
        def __len__(self):
            return len(self.tags)

        def __iter__(self):
            return iter(self.tags)

        def __contains__(self, item):
            return item in self.tags

        def __getitem__(self, key):
            return self.tags[key]

        def __setitem__(self, key, value):
            self.tags[key] = value

        def __delitem__(self, key):
            del self.tags[key]

        def insert(self, key, value):
            self.tags.insert(key, value)

        # Printing and Formatting of tree
        def __repr__(self):
            return f"{len(self.tags)} entries of type {NBTLib.TAGLIST[self.tagID].__name__}"

        # Printing and Formatting of tree
        def valuestr(self):
            return f"[{len(self.tags)} {NBTLib.TAGLIST[self.tagID].__name__}(s)]"

        def __unicode__(self):
            return f'[{", ".join([tag.tag_info() for tag in self.tags])}]'

        def __str__(self):
            return f'[{", ".join([tag.tag_info() for tag in self.tags])}]'

        def pretty_tree(self, indent=0):
            output = [super(NBTLib.TAG_List, self).pretty_tree(indent)]
            if self.tags:
                output.append(("\t" * indent) + "{")
                output.extend([tag.pretty_tree(indent + 1) for tag in self.tags])
                output.append(("\t" * indent) + "}")
            return '\n'.join(output)

    class TAG_Compound(TAG, MutableMapping):
        """
        TAG_Compound, comparable to a collections.OrderedDict with an
        intrinsic name
        """

        def __init__(self, buffer=None, name=None):
            self.id = NBTLib.TAG_COMPOUND
            # TODO: add a value parameter as well
            super(NBTLib.TAG_Compound, self).__init__()
            self.tags = []
            self.name = name
            if buffer:
                self._parse_buffer(buffer)

        # Parsers and Generators
        def _parse_buffer(self, buffer):
            while True:
                typ = NBTLib.TAG_Byte(buffer=buffer)
                if typ.value == NBTLib.TAG_END:
                    # print("found tag_end")
                    break
                name = NBTLib.TAG_String(buffer=buffer).value
                try:
                    tag = NBTLib.TAGLIST[typ.value]()
                except KeyError:
                    raise ValueError(f"Unrecognized tag type {typ.value}")
                tag.name = name
                self.tags.append(tag)
                tag._parse_buffer(buffer)

        def _render_buffer(self, buffer):
            for tag in self.tags:
                NBTLib.TAG_Byte(tag.id)._render_buffer(buffer)
                NBTLib.TAG_String(tag.name)._render_buffer(buffer)
                tag._render_buffer(buffer)
            buffer.write(b'\x00')  # write TAG_END

        # Mixin methods
        def __len__(self):
            return len(self.tags)

        def __iter__(self):
            for key in self.tags:
                yield key.name

        def __contains__(self, key):
            if isinstance(key, int):
                return key <= len(self.tags)
            if isinstance(key, NBTLib.basestring):
                for tag in self.tags:
                    if tag.name == key:
                        return True
                return False
            if isinstance(key, NBTLib.TAG):
                return key in self.tags
            return False

        def __getitem__(self, key):
            if isinstance(key, int):
                return self.tags[key]
            if isinstance(key, NBTLib.basestring):
                for tag in self.tags:
                    if tag.name == key:
                        return tag
                raise KeyError(f"Tag {key} does not exist")

            raise TypeError(
                "key needs to be either name of tag, or index of tag, "
                f"not a {type(key).__name__}")

        def __setitem__(self, key, value):
            assert isinstance(value, NBTLib.TAG), "value must be an nbt.TAG"
            if isinstance(key, int):
                # Just try it. The proper error will be raised if it doesn't work.
                self.tags[key] = value
            elif isinstance(key, NBTLib.basestring):
                value.name = key
                for i, tag in enumerate(self.tags):
                    if tag.name == key:
                        self.tags[i] = value
                        return
                self.tags.append(value)

        def __delitem__(self, key):
            if isinstance(key, int):
                del self.tags[key]
            elif isinstance(key, NBTLib.basestring):
                self.tags.remove(self.__getitem__(key))
            else:
                raise ValueError(
                    "key needs to be either name of tag, or index of tag")

        def keys(self):
            return [tag.name for tag in self.tags]

        def iteritems(self):
            for tag in self.tags:
                yield (tag.name, tag)

        # Printing and Formatting of tree
        def __unicode__(self):
            return "{" + ", ".join([tag.tag_info() for tag in self.tags]) + "}"

        def __str__(self):
            return "{" + ", ".join([tag.tag_info() for tag in self.tags]) + "}"

        def valuestr(self):
            return '{%i Entries}' % len(self.tags)

        def pretty_tree(self, indent=0):
            output = [super(NBTLib.TAG_Compound, self).pretty_tree(indent)]
            if self.tags:
                output.append(("\t" * indent) + "{")
                output.extend([tag.pretty_tree(indent + 1) for tag in self.tags])
                output.append(("\t" * indent) + "}")
            return '\n'.join(output)

    TAGLIST = {TAG_END: _TAG_End, TAG_BYTE: TAG_Byte, TAG_SHORT: TAG_Short,
               TAG_INT: TAG_Int, TAG_LONG: TAG_Long, TAG_FLOAT: TAG_Float,
               TAG_DOUBLE: TAG_Double, TAG_BYTE_ARRAY: TAG_Byte_Array,
               TAG_STRING: TAG_String, TAG_LIST: TAG_List,
               TAG_COMPOUND: TAG_Compound, TAG_INT_ARRAY: TAG_Int_Array,
               TAG_LONG_ARRAY: TAG_Long_Array}

    class NBTFile(TAG_Compound):
        """Represent an NBT file object."""

        def __init__(self, filename=None, buffer=None, fileobj=None):
            """
            Create a new NBTFile object.
            Specify either a filename, file object or data buffer.
            If filename of file object is specified, data should be GZip-compressed.
            If a data buffer is specified, it is assumed to be uncompressed.
            If filename is specified, the file is closed after reading and writing.
            If file object is specified, the caller is responsible for closing the
            file.
            """
            super(NBTLib.NBTFile, self).__init__()
            self.filename = filename
            self.type = NBTLib.TAG_Byte(self.id)
            closefile = True
            # make a file object
            if filename:
                self.filename = filename
                self.file = GzipFile(filename, 'rb')
            elif buffer:
                if hasattr(buffer, 'name'):
                    self.filename = buffer.name
                self.file = buffer
                closefile = False
            elif fileobj:
                if hasattr(fileobj, 'name'):
                    self.filename = fileobj.name
                self.file = GzipFile(fileobj=fileobj)
            else:
                self.file = None
                closefile = False
            # parse the file given initially
            if self.file:
                self.parse_file()
                if closefile:
                    # Note: GzipFile().close() does NOT close the fileobj,
                    # So we are still responsible for closing that.
                    try:
                        self.file.close()
                    except (AttributeError, IOError):
                        pass
                self.file = None

        def parse_file(self, filename=None, buffer=None, fileobj=None):
            """Completely parse a file, extracting all tags."""
            if filename:
                self.file = GzipFile(filename, 'rb')
            elif buffer:
                if hasattr(buffer, 'name'):
                    self.filename = buffer.name
                self.file = buffer
            elif fileobj:
                if hasattr(fileobj, 'name'):
                    self.filename = fileobj.name
                self.file = GzipFile(fileobj=fileobj)
            if self.file:
                try:
                    typ = NBTLib.TAG_Byte(buffer=self.file)
                    if typ.value == self.id:
                        name = NBTLib.TAG_String(buffer=self.file).value
                        self._parse_buffer(self.file)
                        self.name = name
                        self.file.close()
                    else:
                        raise NBTLib.MalformedFileError(
                            "First record is not a Compound Tag")
                except StructError:
                    raise NBTLib.MalformedFileError(
                        "Partial File Parse: file possibly truncated.")
            else:
                raise ValueError(
                    "NBTFile.parse_file(): Need to specify either a "
                    "filename or a file object"
                )

        def write_file(self, filename=None, buffer=None, fileobj=None):
            """Write this NBT file to a file."""
            closefile = True
            if buffer:
                self.filename = None
                self.file = buffer
                closefile = False
            elif filename:
                self.filename = filename
                self.file = GzipFile(filename, "wb")
            elif fileobj:
                self.filename = None
                self.file = GzipFile(fileobj=fileobj, mode="wb")
            elif self.filename:
                self.file = GzipFile(self.filename, "wb")
            elif not self.file:
                raise ValueError(
                    "NBTFile.write_file(): Need to specify either a "
                    "filename or a file object"
                )
            # Render tree to file
            NBTLib.TAG_Byte(self.id)._render_buffer(self.file)
            NBTLib.TAG_String(self.name)._render_buffer(self.file)
            self._render_buffer(self.file)
            # make sure the file is complete
            try:
                self.file.flush()
            except (AttributeError, IOError):
                pass
            if closefile:
                try:
                    self.file.close()
                except (AttributeError, IOError):
                    pass

        def __repr__(self):
            """
            Return a string (ascii formated for Python 2, unicode
            for Python 3) describing the class, name and id for
            debugging purposes.
            """
            if self.filename:
                return (f"<{self.__class__.__name__}({self.filename}) "
                    f"with {NBTLib.TAG_Compound.__name__}({self.name}) at 0x{id(self):x}>")

            return (f"<{self.__class__.__name__} with {NBTLib.TAG_Compound.__name__}"
                f"({self.name}) at 0x{id(self):x}>")
