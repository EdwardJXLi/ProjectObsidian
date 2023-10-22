##################################################################
#
# A custom replace function that ignores targets with backslashes.
#
##################################################################

import re


def restricted_replace(input_str: str, search_str: str, replace_str: str, regex_flags=0):
    # Escape the search string to handle special characters
    search_str = re.escape(search_str)

    # Define a regular expression pattern to match values without a leading backslash
    pattern = re.compile(rf'(?<!\\){search_str}', flags=regex_flags)

    # Use re.sub to replace the matched values
    result = re.sub(pattern, replace_str, input_str)

    return result
