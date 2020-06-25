import collections
import copy
import re
import subprocess


def shell(cmd, check=True, stdin=None, stdout=None, stderr=None):
    """Runs a subprocess shell with check=True by default"""
    return subprocess.run(
        cmd, shell=True, check=check, stdin=stdin, stdout=stdout, stderr=stderr
    )


def _equals(a, b, match=False):
    """True if a equals b. If match is True, perform a regex match

    If b is a regex ``Pattern``, applies regex matching
    """
    if match:
        return re.match(b, a) is not None if isinstance(a, str) else False
    else:
        return a == b


class FilterableUserList(collections.UserList):
    """
    A collections.UserList that is filterable and groupable by the objects
    in the list.
    """

    def filter(self, attr, value, match=False):
        """Filter elements by an attribute.

        Args:
            attr (str): The name of the attribute.
            value (str|bool): The value to filter by.
            match (bool, default=False): Treat ``value`` as a regex pattern and
                match against it.

        Returns:
            ``self.__class__``: A copy of the filtered list object.
        """
        obj = copy.copy(self)
        obj.data = [
            element
            for element in self.data
            if _equals(getattr(element, attr), value, match=match)
        ]
        return obj

    def exclude(self, attr, value, match=False):
        """Exclude elements by an attribute.

        Args:
            attr (str): The name of the attribute.
            value (str|bool): The value to exclude by.
            match (bool, default=False): Treat ``value`` as a regex pattern and
                match against it.

        Returns:
            ``self.__class__``: A copy of the excluded list object.
        """
        obj = copy.copy(self)
        obj.data = [
            element
            for element in self.data
            if not _equals(getattr(element, attr), value, match=match)
        ]
        return obj

    def intersect(self, attr, values):
        """Return elements whose attributes intersects a set of values.

        Args:
            attr (str): The attribute to filter by.
            values (Set[str]): The values the attribute must be in.

        Returns:
            ``self.__class__``: A copy of the filtered list object.
        """
        obj = copy.copy(self)
        obj.data = [
            element
            for element in self.data
            if getattr(element, attr) in values
        ]
        return obj

    def group(
        self,
        attr,
        ascending_keys=False,
        descending_keys=False,
        none_key_first=False,
        none_key_last=False,
    ):
        """Group elements by an attribute.

        Args:
            attr (str): The attribute to group by.
            ascending_keys (bool, default=False): Sort the keys in ascending
                order.
            descending_keys (bool, default=False): Sort the keys in descending
                order.
            none_key_first (bool, default=False): Make the "None" key be first.
            none_key_last (bool, default=False): Make the "None" key be last.

        Returns:
            `collections.OrderedDict`: A dictionary of ``self.__class__`` keyed
            on groups.
        """
        if any([ascending_keys, descending_keys]) and not any(
            [none_key_first, none_key_last]
        ):
            # If keys are sorted, default to making the "None" key last
            none_key_last = True

        # Get the natural ordering of the keys
        keys = list(
            collections.OrderedDict(
                (getattr(commit, attr), True) for commit in self
            ).keys()
        )

        # Re-sort the keys
        if any([ascending_keys, descending_keys]):
            sorted_keys = sorted(
                (k for k in keys if k is not None), reverse=descending_keys
            )
            if None in keys:
                sorted_keys.append(None)

            keys = sorted_keys

        # Change the ordering of the "None" key
        if any([none_key_first, none_key_last]) and None in keys:
            keys.remove(None)
            keys.insert(0 if none_key_first else len(keys), None)

        return collections.OrderedDict(
            (key, self.filter(attr, key)) for key in keys
        )
