import copy
from packages.action_core.world import Frame,Action
from packages.shared_world.contextual_rewrite import ContextualRewrite,context


def record(enabled):
    f=Frame([1,0,2 if enabled else 0],[.3,0,0],[[1,0,0],[0,0,0],[0,0,0]],
            [[0,0,0],[0,0,0],[0,1,0]],('n0','n1','n2'))
    after=copy.deepcopy(f)
    if enabled:
        after.kinds=[0,1,2];after.sizes=[0,.3,0];after.equal=[[0,0,0],[0,1,0],[0,0,0]]
    return {'before':f.to_dict(),'after':after.to_dict(),'action':Action('opaque',('n0','n1')).to_dict()}


def test_context_distinguishes_observed_structure_not_action_name():
    rows=[record(False),record(True)];model=ContextualRewrite(rows)
    for row in rows:
        f=Frame.from_dict(row['before']);a=Action.from_dict(row['action'])
        prediction=model.predict(f,a)
        assert all(len(v)==1 for _,_,v in prediction)
        kinds={address[0]:v[0] for field,address,v in prediction if field=='kind'}
        assert list(kinds.values())==row['after']['kinds']
        assert all(not v for _,_,v in model.predict(f,Action('other',a.args)))


def test_hidden_contradiction_does_not_invent_a_condition():
    row=record(True);conflict=copy.deepcopy(row);conflict['after']=conflict['before']
    model=ContextualRewrite([row,conflict])
    assert all(not v for field,_,v in model.predict(Frame.from_dict(row['before']),Action('opaque',('n0','n1'))) if field=='kind')


def test_neighbor_features_invariant_to_node_names_and_permutation():
    f=Frame.from_dict(record(True)['before']);order=[2,0,1]
    g=Frame([f.kinds[i] for i in order],[f.sizes[i] for i in order],
        [[f.equal[i][j] for j in order] for i in order],
        [[f.parent[i][j] for j in order] for i in order],('n0','n1','n2'))
    assert context(f,(0,1))==context(g,(1,2))


def test_equal_degree_does_not_alias_distinct_argument_relations():
    from packages.shared_world.index_rewrite import fields,remap
    f=Frame([1]*4,[.2]*4,[[1]*4 for _ in range(4)],[[0]*4 for _ in range(4)],
        ('n0','n1','n2','n3'),{'r_opaque':[[1,1,0,0],[1,1,0,0],[0,0,1,1],[0,0,1,1]]})
    # Every node has equal degree; only its relation to the selected argument differs.
    assert context(f,(0,1))!=context(f,(0,2))
    rows=[]
    for destination in (1,2):
        after=copy.deepcopy(f)
        if destination==1:
            for field,values in fields(f).items():
                changed=remap(values,(0,1),(-2,-1))
                if field=='kind':after.kinds=changed
                elif field=='size':after.sizes=changed
                elif field=='equal':after.equal=changed
                else:after.relations[field]=changed
        rows.append({'before':f.to_dict(),'after':after.to_dict(),
                     'action':Action('uninterpreted',('n0',f'n{destination}')).to_dict()})
    model=ContextualRewrite(rows)
    for row in rows:
        prediction=model.predict(f,Action.from_dict(row['action']))
        assert all(len(v)==1 for _,_,v in prediction)
