library(tidygraph)
library(tidyverse)
library(igraph)

names = read_tsv('~/Desktop/DeleteMe/hpnames.txt')
atts = read_tsv('~/Desktop/DeleteMe/hpattributes.txt')
df = merge(names, atts)

# Create a graph object from matrix

edge_mx = as.matrix(read_table('~/Desktop/DeleteMe/hpbook5.txt', col_names = FALSE))

G = graph_from_adjacency_matrix(edge_mx, mode = 'directed') |> as_tbl_graph()

# Add attributes to nodes

G = G |> activate(nodes) |>
 select(-name) |>
 mutate(id = 1:length(df$name))

G = G |> activate(nodes) |>
    left_join(df, by = 'id')

G = G |>
    activate(nodes) |>
    mutate(house = case_match(house,
                              1 ~ 'Gryffindor',
                              2 ~ 'Hufflepuff',
                              3 ~ 'Ravenclaw',
                              4 ~ 'Slytherin'
                              )) |>
    mutate(gender = case_match(gender,
                            1 ~ 'male',
                            2 ~ 'female'))

G |> activate(nodes) |>
as_tibble() |>
write_csv('./hp_node_atts.csv')


G |> activate(edges) |>
as_tibble() |>
write_csv('./hp_edgelist.csv')
