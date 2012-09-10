from ..extern.tabulartext import PrettyTable


"""
This module defines a framework for filtering Trees.
The user must write a class which inherits from Filter and
"""


class Filter(object):
    """
    The base class from which all filter classes must inherit from.
    The derived class must override the passes method which returns True
    if ths event passes and returns False if not.
    The number of passing and failing events are recorded and may be used
    later to create a cut-flow.
    """
    def __init__(self,
            hooks=None,
            passthrough=False,
            name=None,
            count_funcs=None):

        self.total = 0
        self.passing = 0
        self.count_funcs_total = {}
        self.count_funcs_passing = {}

        if count_funcs is not None:
            self.count_funcs = count_funcs
        else:
            self.count_funcs = {}

        for name in self.count_funcs.iterkeys():
            self.count_funcs_total[name] = 0.
            self.count_funcs_passing[name] = 0.

        self.details = {}
        if name is None:
            self.name = self.__class__.__name__
        else:
            self.name = name

        self.hooks = hooks
        self.passthrough = passthrough
        self.was_passed = False

    def __str__(self):

        return self.__repr__()

    def __getstate__(self):

        return {"name": self.name,
                "total": self.total,
                "passing": self.passing,
                "details": self.details,
                "count_funcs_total": self.count_funcs_total,
                "count_funcs_passing": self.count_funcs_passing}

    def __setstate__(self, state):

        self.name = state['name']
        self.total = state['total']
        self.passing = state['passing']
        self.details = state['details']
        self.count_funcs_total = state['count_funcs_total']
        self.count_funcs_passing = state['count_funcs_passing']

    def __repr__(self):

        return "Filter %s\n" % (self.name) + \
               "Total: %i\n" % (self.total) + \
               "Pass:  %i" % (self.passing)

    @classmethod
    def add(cls, left, right):

        if left.name != right.name:
            raise ValueError("Attemping to add filters with different names")
        newfilter = Filter()
        newfilter.name = left.name
        newfilter.total = left.total + right.total
        newfilter.passing = left.passing + right.passing
        newfilter.details = dict([
            (detail, left.details[detail] + right.details[detail])
            for detail in left.details.keys()])
        return newfilter

    def __add__(self, other):

        return Filter.add(self, other)

    def passed(self, event):

        self.total += 1
        self.passing += 1

        for name, func in self.count_funcs.iteritems():
            count = func(event)
            self.count_funcs_total[name] += count
            self.count_funcs_passing[name] += count

        self.was_passed = True

    def failed(self, event):

        self.total += 1

        for name, func in self.count_funcs.iteritems():
            count = func(event)
            self.count_funcs_total[name] += count

        self.was_passed = False


class FilterHook(object):

    def __init__(self, target, args):

        self.target = target
        self.args = args

    def __call__(self):

        self.target(*self.args)


class EventFilter(Filter):

    def __call__(self, event):

        if self.passthrough:
            if self.hooks:
                for hook in self.hooks:
                    hook()
            self.passed(event)
            return True
        _passes = self.passes(event)
        if _passes is None:
            # event is not counted in total
            return False
        elif _passes:
            if self.hooks:
                for hook in self.hooks:
                    hook()
            self.passed(event)
            return True
        self.failed(event)
        return False

    def passes(self, event):
        """
        You should override this method in your derived class
        """
        return True

    def finalize(self):
        """
        You should override this method in your derived class
        """
        pass


class ObjectFilter(Filter):

    def __init__(self, count_events=False, **kwargs):

        self.count_events = count_events
        super(ObjectFilter, self).__init__(**kwargs)

    def __call__(self, event, collection):

        self.was_passed = False
        if self.count_events:
            self.total += 1
        else:
            self.total += len(collection)
        if not self.passthrough:
            collection = self.filtered(event, collection)
        if len(collection) > 0:
            self.was_passed = True
            if self.count_events:
                self.passing += 1
            else:
                self.passing += len(collection)
        return collection

    def filtered(self, event, collection):
        """
        You should override this method in your derived class
        """
        return collection


class FilterList(list):
    """
    Creates a list of Filters for convenient evaluation of a sequence of Filters.
    """
    @classmethod
    def merge(cls, list1, list2):

        if not isinstance(list1, list):
            raise TypeError("list1 must be a FilterList or list")
        if not isinstance(list2, list):
            raise TypeError("list2 must be a FilterList or list")
        filterlist = FilterList()
        for f1, f2 in zip(list1, list2):
            if type(f1) is dict:
                _f1 = Filter()
                _f1.__setstate__(f1)
                f1 = _f1
            if type(f2) is dict:
                _f2 = Filter()
                _f2.__setstate__(f2)
                f2 = _f2
            filterlist.append(f1 + f2)
        return filterlist

    @property
    def total(self):

        if len(self) > 0:
            return self[0].total
        return 0

    @property
    def passing(self):

        if len(self) > 0:
            return self[-1].passing
        return 0

    def basic(self):
        """
        Return all filters as simple dicts for pickling.
        Removes all dependence on this module.
        """
        return [filter.__getstate__() for filter in self]

    def __setitem__(self, filter):

        if not isinstance(filter, (Filter, dict)):
            raise TypeError(
                    "FilterList can only hold objects "
                    "inheriting from Filter or dict")
        super(FilterList, self).__setitem__(filter)

    def append(self, filter):

        if not isinstance(filter, (Filter, dict)):
            raise TypeError(
                    "FilterList can only hold objects "
                    "inheriting from Filter or dict")
        super(FilterList, self).append(filter)

    def __str__(self):

        return self.__repr__()

    def __repr__(self):

        if len(self) > 0:
            table = PrettyTable(["Filter", "Pass"])
            table.align["Filter"] = "l"
            table.align["Pass"] = "l"
            table.add_row(["Total", self[0].total])
            for filter in self:
                table.add_row([filter.name, filter.passing])
            _str = str(table)
            for filter in self:
                if filter.details:
                    _str += "\n%s Details\n" % filter.name
                    details_table = PrettyTable(["Detail", "Value"])
                    for key, value in filter.details.items():
                        details_table.add_row([key, value])
                    _str += str(details_table)
            return _str
        return "Empty FilterList"


class EventFilterList(FilterList):

    def __call__(self, event):

        for filter in self:
            if not filter(event):
                return False
        return True

    def __setitem__(self, filter):

        if not isinstance(filter, EventFilter):
            raise TypeError(
                    "EventFilterList can only hold objects "
                    "inheriting from EventFilter")
        super(EventFilterList, self).__setitem__(filter)

    def append(self, filter):

        if not isinstance(filter, EventFilter):
            raise TypeError(
                    "EventFilterList can only hold objects "
                    "inheriting from EventFilter")
        super(EventFilterList, self).append(filter)

    def finalize(self):

        for filter in self:
            filter.finalize()


class ObjectFilterList(FilterList):

    def __call__(self, event, collection):

        passing_objects = collection
        for filter in self:
            passing_objects = filter(event, passing_objects)
            if not passing_objects:
                return []
        return passing_objects

    def __setitem__(self, filter):

        if not isinstance(filter, ObjectFilter):
            raise TypeError(
                    "ObjectFilterList can only hold objects "
                    "inheriting from ObjectFilter")
        super(ObjectFilterList, self).__setitem__(filter)

    def append(self, filter):

        if not isinstance(filter, ObjectFilter):
            raise TypeError(
                    "ObjectFilterList can only hold objects "
                    "inheriting from ObjectFilter")
        super(ObjectFilterList, self).append(filter)
