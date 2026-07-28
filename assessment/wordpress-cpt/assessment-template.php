<?php
/**
 * Register Assessment Template CPT and Difficulty Level taxonomy
 */

// ── Part 1: Register Custom Post Type ──────────────────────────────────

function register_assessment_template_cpt() {
    register_post_type('assessment_template', [
        // TODO: labels
        'public'            =>  false,
        'show_ui'           =>  true,
        'show_in_rest'      =>  true,
        'show_in_graphql'   =>  true,
        'graphql_single_name'=> 'assesmentTemplate',
        'supports'          =>  ['title','editor','custom'],
        'labels'            =>  [
            'name'          =>  'Assesment Templates',
            'singular_name' =>  'Assesment Template',
        ],

    ]);
}
add_action('init', 'register_assessment_template_cpt');


// ── Part 2: Register Taxonomy ──────────────────────────────────────────

function register_difficulty_level_taxonomy() {
    register_taxonomy('difficulty_level', 'assessment_template', [
        // TODO: not doing labels
        // TODO: hierarchical — is it like categories (true) or tags (false)?
        // TODO: show_in_rest
        // TODO: show_in_graphql + graphql names

        'show_in_rest'      =>  true,
        'show_in_graphql'   =>  true,
        'hierarchical'      =>  ['begginer','inter','advance'],
    ]);
}
add_action('init', 'register_difficulty_level_taxonomy');


// ── Part 4: Expose question_prompts to GraphQL ────────────────────────

// Option A: register_graphql_field() — manually resolve the meta value
//
// Syntax guide:
//   register_graphql_field('TypeName', 'fieldName', [
//       'type'        => 'String',          // GraphQL type
//       'description' => 'What this field is',
//       'resolve'     => function($post) {
//           // get_post_meta($post->ID, 'meta_key', true) fetches the value
//           // json_decode() turns a JSON string into a PHP array
//           // return the decoded value
//       },
//   ]);
//
// The TypeName for your CPT is the graphql_single_name with capital first letter
// e.g. 'AssessmentTemplate'
//
// The type for an array of strings in GraphQL is: ['list_of' => 'String']

function register_graphql_question_prompts_field(){
    register_graphql_field("QuestionPrompt","questionPrompt",[
        'type'          =>  'String',
        'description'   =>  'description',
        'resolve'       =>  function($post){
            $meta = get_post_meta($post->ID,'meta-key',true);
            $decodedMeta = json_decode(meta);
            return $decodedMeta;
        }, ]

        //and the ql names 

    );
}

function register_question_prompts_field() {
    register_graphql_field(/* TODO: type name */, 'questionPrompts', [
        'type'        => /* TODO: what GraphQL type? array of strings */,
        'description' => 'Array of question prompt strings',
        'resolve'     => function($post) {
            // TODO: get the meta, decode the JSON, return it
        },
    ]);
}
add_action('graphql_register_types', 'register_question_prompts_field');
