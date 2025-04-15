# Version 1.0.0

class PrettyTableLite():
    def __init__(self):
        self._data = [[]]

    # Getters and Setters for field_names
    @property
    def field_names(self):
        return self._data[0]

    @field_names.setter
    def field_names(self, fields):
        if self.field_names:
            raise Exception("Fields Value Has Already Been Set")
        self._data[0] = fields

    def add_row(self, row):
        if len(row) != len(self._data[0]):
            raise Exception(f"Field name list has incorrect number of values (Expected {len(row)} got {len(self._data[0])})")
        self._data.append(row)

    # Internal Generation Function to Format Row
    def _generateRow(self, row):
        return '|'.join([
            ' ' + str(self._data[row][col]).ljust(self.maxCellWidth[col] + 1)  # Generate And Pad Values
            for col in range(len(self._data[0]))  # Loop Through All Values
        ])

    def generate(self):
        self.maxCellWidth = [
            max(
                len(str(self._data[row][col]))  # Get Length Of Each String
                for row in range(len(self._data))  # Loop Through All Rows
            )  # Find Longest String
            for col in range(len(self._data[0]))  # Loop Through All Cols
        ]
        divider = '+' + '+'.join(['-' * (width + 2) for width in self.maxCellWidth]) + '+'  # Generate Divider For Top, Middle, and Bottom
        returnStr = []
        returnStr.append(divider)
        returnStr.append('|' + self._generateRow(0) + '|')  # Add Header
        returnStr.append(divider)
        for row in range(1, len(self._data)):
            returnStr.append('|' + self._generateRow(row) + '|')  # Add Values
        returnStr.append(divider)
        return '\n'.join(returnStr)

    def __str__(self):
        return self.generate()
