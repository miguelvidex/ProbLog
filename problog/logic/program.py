from __future__ import print_function

from .basic import Term, Var, And, Or, Not, Clause, LogicProgram


class ClauseDB(LogicProgram) :
    """Compiled logic program.
    
    A logic program is compiled into a table of instructions.
    
    The following instruction types are available:
    
    * and ( child1, child2 )
    * or  ( children )
    * not ( child )
    * call ( arguments )
    * clause ( definitions )
    * def ( head arguments, body node, variables in body )
    * fact ( argument )
    * *empty* ( undefined (e.g. builtin) )
    
    .. todo:: 
        
        annotated disjunction are not supported yet
    
    """
    
    def __init__(self) :
        LogicProgram.__init__(self)
        self.__nodes = []   # list of nodes
        self.__heads = {}   # head.sig => node index
    
    def getNode(self, index) :
        """Get the instruction node at the given index.
        
        :param index: index of the node to retrieve
        :type index: :class:`int`
        :returns: requested node
        :rtype: :class:`tuple`
        :raises IndexError: the given index does not point to a node
        
        """
        return self.__nodes[index]
        
    def _setNode(self, index, node_type, node_content, *node_extra) :
        self.__nodes[index] = (node_type, node_content) + node_extra
        
    def _appendNode(self, *node_extra) :
        index = len(self.__nodes)
        self.__nodes.append( node_extra )
        return index
    
    def _getHead(self, head) :
        return self.__heads.get( head.signature )
        
    def _setHead(self, head, index) :
        self.__heads[ head.signature ] = index
    
    def _addHead( self, head, create=True ) :
        node = self._getHead( head )
        if node == None :
            if create :
                node = self._appendNode( 'clause', [], head.functor )
            else :
                node = self._appendNode()
            self._setHead( head, node )
        return node
    
    def _addClauseNode( self, head, body_node, body_vars ) :
        """Add a clause node."""
        subnode = self._addDef( head, body_node, body_vars )        
        return self._addClauseBody( head, subnode )
        
    def addFact( self, term) :
        """Add a fact to the database.
        
        :param term: term to add
        :type term: :class:`.basic.Term`
        :returns: location of the fact in the database
        :rtype: :class:`int`
        """
        subnode = self._appendNode('fact', term.args)
        return self._addClauseBody( term, subnode )
                
    def _addClauseBody( self, head, subnode ) :
        index = self._addHead( head )
        def_node = self.getNode(index)
        if not def_node :
            clauses = []
            self._setNode( index, 'clause', clauses, head.functor )
        else :
            clauses = def_node[1]
        clauses.append( subnode )
        return index
            
    def _addDef( self, term, subnode, body_vars ) :
        """Add a *definition* node."""
        return self._appendNode('def', subnode, term.args, body_vars)
                
    def _addCall( self, term ) :
        """Add a *call* node."""
        node = self._addHead(term, create=False)
        #print (type(term), type(term.functor), term)
        return self._appendNode( 'call', node, term.args, term.functor )
        
    def _addAnd( self, op1, op2, usedVars=[] ) :
        """Add an *and* node."""
        return self._appendNode( 'and', (op1,op2) )
        
    def _addNot( self, op1, usedVars=[] ) :
        """Add a *not* node."""
        return self._appendNode( 'not', op1 )        
        
    def _addOr( self, op1, op2, usedVars=[] ) :
        """Add an *or* node."""
        return self._appendNode( 'or', (op1,op2) )
    
    def find(self, head ) :
        """Find the clause node corresponding to the given head.
        
        :param head: clause head to match
        :type head: :class:`.basic.Term`
        :returns: location of the clause node in the database, returns ``None`` if no such node exists
        :rtype: :class:`int` or ``None``
        """
        return self._getHead( head )
       
    def __repr__(self) :
        s = ''
        for i,n in enumerate(self.__nodes) :
            s += '%s: %s\n' % (i,n)
        s += str(self.__heads)
        return s
        
    def addClause(self, clause) :
        """Add a clause to the database.
        
        :param clause: Clause to add
        :type clause: :class:`.Clause`
        :returns: location of the definition node in the database
        :rtype: :class:`int`
        """
        return self._compile( clause )
    
    def _compile(self, struct, variables=None) :
        if variables == None : variables = _AutoDict()
        
        if isinstance(struct, And) :
            op1, op1Vars = self._compile(struct.op1, variables)
            op2, op2Vars = self._compile(struct.op2, variables)
            opVars = (op1Vars | op2Vars)
            return self._addAnd( op1, op2, usedVars = opVars), opVars
        elif isinstance(struct, Or) :
            op1, op1Vars = self._compile(struct.op1, variables)
            op2, op2Vars = self._compile(struct.op2, variables)
            opVars = (op1Vars | op2Vars)
            return self._addOr( op1, op2, usedVars = opVars), opVars
        elif isinstance(struct, Not) :
            child, opVars = self._compile(struct.child, variables)
            return self._addNot( child, usedVars = opVars), opVars
        elif isinstance(struct, Clause) :
            new_head = struct.head.apply(variables)
            body_node, usedVars = self._compile(struct.body, variables)
            res = self._addClauseNode(new_head, body_node, len(variables))
            return res
        elif isinstance(struct, Term) :
            return self._addCall( struct.apply(variables) ), variables.usedVars()
        else :
            raise ValueError("Unknown structure type: '%s'" % struct )
    
    def _create_vars(self, term) :
        if type(term) == int :
            return Var('V_' + str(term))
        else :
            args = [ self._create_vars(arg) for arg in term.args ]
            return term.withArgs(*args)
        
    def _extract(self, node_id, func=None) :
        node = self.getNode(node_id)
        if not node :
            raise ValueError("Unexpected empty node.")    
        if node[0] == 'fact' :
            return Term(func, *node[1])
        elif node[0] == 'def' :
            head = self._create_vars( Term(func,*node[2]) )
            return Clause( head, self._extract(node[1]))
        elif node[0] == 'call' :
            func = node[3]
            args = node[2]
            return self._create_vars( Term(func, *args) )
        elif node[0] == 'and' :
            a,b = node[1]
            return And( self._extract(a), self._extract(b) )
        elif node[0] == 'or' :
            a,b = node[1]
            return Or( self._extract(a), self._extract(b) )
        else :
            raise ValueError("Unknown node type: '%s'" % node[0])    
        
        
    def __iter__(self) :
        for node in self.__nodes :
            if node and node[0] == 'clause' :
                for defnode in node[1] :
                    yield self._extract( defnode, node[2] )
        
class _AutoDict(dict) :
    
    def __init__(self) :
        dict.__init__(self)
        self.__record = set()
    
    def __getitem__(self, key) :
        value = self.get(key)
        if value == None :
            value = len(self)
            self[key] = value
        self.__record.add(value)
        return value
        
    def usedVars(self) :
        result = set(self.__record)
        self.__record.clear()
        return result
        
    def define(self, key) :
        if not key in self :
            value = len(self)
            self[key] = value
            